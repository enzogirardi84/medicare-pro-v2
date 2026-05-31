#!/usr/bin/env python3
"""Data Tiering: archivos frios a S3/R2 en formato Parquet comprimido.
Los datos GPS > 3 meses se exportan a Parquet y se suben a Cold Storage.
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from core.app_logging import log_event


class DataTieringWorker:
    """Worker de Data Tiering: Hot (PostgreSQL) -> Cold (S3/Parquet).

    Los datos GPS mayores a 3 meses se exportan a archivos Parquet
    comprimidos con zstd y se suben a AWS S3 / Cloudflare R2.
    """

    HOT_RETENTION_DAYS = 90
    CHUNK_SIZE = 50000  # Filas por archivo Parquet

    def __init__(self, db_url: str):
        self.db_url = db_url
        self._s3_client = None

    def _get_s3_client(self):
        """Cliente S3 lazy (boto3 o fallback local)."""
        if self._s3_client is None:
            try:
                import boto3
                self._s3_client = boto3.client(
                    "s3",
                    endpoint_url=os.environ.get("S3_ENDPOINT"),
                    region_name=os.environ.get("S3_REGION", "us-east-1"),
                )
            except ImportError:
                log_event("tiering", "boto3 no instalado: usando directorio local")
                self._s3_client = "local"
        return self._s3_client

    async def export_checkins_frios(self) -> int:
        """Exporta check-ins GPS anteriores a HOT_RETENTION_DAYS a Parquet.

        Returns:
            Cantidad de filas exportadas.
        """
        import asyncpg

        cutoff = datetime.utcnow() - timedelta(days=self.HOT_RETENTION_DAYS)
        conn = await asyncpg.connect(self.db_url)
        total_exportadas = 0
        offset = 0

        try:
            while True:
                rows = await conn.fetch("""
                    SELECT id, tenant_id, profesional_id, paciente_id,
                           ST_X(punto::GEOMETRY) as lon,
                           ST_Y(punto::GEOMETRY) as lat,
                           timestamp, source
                    FROM checkins_gps
                    WHERE timestamp < $1
                    ORDER BY timestamp
                    LIMIT $2 OFFSET $3
                """, cutoff, self.CHUNK_SIZE, offset)

                if not rows:
                    break

                records = [dict(r) for r in rows]
                self._escribir_parquet(records, cutoff)
                total_exportadas += len(records)
                offset += len(rows)
                log_event("tiering", f"exportadas {total_exportadas} filas...")

            log_event("tiering", f"Total exportado: {total_exportadas}")
            return total_exportadas

        finally:
            await conn.close()

    def _escribir_parquet(self, records: list[dict[str, Any]], cutoff: datetime) -> None:
        """Escribe un archivo Parquet y lo sube a S3/local."""
        import pyarrow as pa
        import pyarrow.parquet as pq

        schema = pa.schema([
            ("id", pa.int64()),
            ("tenant_id", pa.string()),
            ("profesional_id", pa.string()),
            ("paciente_id", pa.string()),
            ("lon", pa.float64()),
            ("lat", pa.float64()),
            ("timestamp", pa.timestamp("us")),
            ("source", pa.string()),
        ])

        table = pa.Table.from_pylist(records, schema=schema)
        buf = io.BytesIO()
        pq.write_table(table, buf, compression="zstd", row_group_size=10000)
        buf.seek(0)
        parquet_bytes = buf.getvalue()

        # Nombre de archivo: tenant/fecha/parte.parquet
        fecha = cutoff.strftime("%Y/%m")
        filename = f"checkins_frios/{fecha}/{int(time.time())}_{len(records)}.parquet"

        s3 = self._get_s3_client()
        bucket = os.environ.get("S3_COLD_BUCKET", "medicare-cold-storage")

        if s3 == "local":
            local_path = Path(f"storage/cold/{filename}")
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(parquet_bytes)
            log_event("tiering", f"Local: {local_path}")
        else:
            s3.put_object(
                Bucket=bucket,
                Key=filename,
                Body=parquet_bytes,
                StorageClass="DEEP_ARCHIVE",
                Metadata={"tier": "cold", "exported_at": str(time.time())},
            )
            log_event("tiering", f"S3: s3://{bucket}/{filename}")

    async def limpiar_checkins_frios(self) -> int:
        """Elimina de PostgreSQL las filas exportadas exitosamente."""
        import asyncpg
        cutoff = datetime.utcnow() - timedelta(days=self.HOT_RETENTION_DAYS)
        conn = await asyncpg.connect(self.db_url)
        try:
            result = await conn.execute(
                "DELETE FROM checkins_gps WHERE timestamp < $1",
                cutoff,
            )
            log_event("tiering", f"Limpiadas {result} filas viejas")
            return int(result.split()[-1]) if result else 0
        finally:
            await conn.close()


if __name__ == "__main__":
    import asyncio
    db_url = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/medicare")
    worker = DataTieringWorker(db_url)
    asyncio.run(worker.export_checkins_frios())
    asyncio.run(worker.limpiar_checkins_frios())
