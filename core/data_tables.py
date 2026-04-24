"""
Tablas de datos mejoradas para MediCare.
Ordenamiento, filtros, exportación rápida y selección múltiple.
"""
import pandas as pd
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass
from datetime import datetime
import html

import streamlit as st


@dataclass
class TableColumn:
    """Definición de una columna de tabla."""
    key: str
    label: str
    sortable: bool = True
    filterable: bool = True
    width: Optional[str] = None
    formatter: Optional[Callable] = None  # Función para formatear el valor
    align: str = "left"  # left, center, right


class DataTable:
    """
    Tabla de datos interactiva con ordenamiento y filtros.
    """
    
    def __init__(
        self,
        data: List[Dict[str, Any]],
        columns: List[TableColumn],
        key: str = "data_table",
        rows_per_page: int = 10,
    ):
        self.data = data
        self.columns = columns
        self.key = key
        self.rows_per_page = rows_per_page
        
        # Estado
        self._sort_key = f"{key}_sort"
        self._sort_order_key = f"{key}_sort_order"
        self._filters_key = f"{key}_filters"
        self._page_key = f"{key}_page"
        self._selected_key = f"{key}_selected"
    
    def render(
        self,
        enable_sorting: bool = True,
        enable_filtering: bool = True,
        enable_pagination: bool = True,
        enable_selection: bool = False,
        on_select: Optional[Callable[[List[str]], None]] = None,
        empty_message: str = "No hay datos para mostrar",
    ) -> List[Dict[str, Any]]:
        """
        Renderizar la tabla completa.
        
        Returns:
            Lista de datos filtrados y ordenados
        """
        if not self.data:
            st.info(empty_message)
            return []
        
        # Inyectar CSS
        self._inject_css()
        
        # Filtros
        filtered_data = self._apply_filters() if enable_filtering else self.data
        
        # Ordenamiento
        sorted_data = self._apply_sorting(filtered_data) if enable_sorting else filtered_data
        
        # Mostrar controles
        if enable_filtering:
            self._render_filters()
        
        # Estadísticas
        st.caption(f"📊 Mostrando {len(sorted_data)} de {len(self.data)} registros")
        
        # Paginación
        if enable_pagination:
            paginated_data, total_pages = self._apply_pagination(sorted_data)
        else:
            paginated_data = sorted_data
            total_pages = 1
        
        # Renderizar tabla
        self._render_table_header()
        self._render_table_rows(paginated_data, enable_selection)
        
        # Paginación UI
        if enable_pagination and total_pages > 1:
            self._render_pagination_controls(total_pages)
        
        # Selección
        if enable_selection and on_select:
            selected = self._get_selected()
            if selected:
                on_select(selected)
        
        return paginated_data
    
    def _inject_css(self):
        """Inyectar CSS para la tabla."""
        st.markdown("""
        <style>
        .mc-data-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
            margin-top: 1rem;
        }
        
        .mc-data-table th {
            background: rgba(30, 41, 59, 0.8);
            color: #f1f5f9;
            font-weight: 600;
            padding: 0.75rem;
            text-align: left;
            border-bottom: 2px solid rgba(148, 163, 184, 0.2);
            cursor: pointer;
            user-select: none;
            white-space: nowrap;
        }
        
        .mc-data-table th:hover {
            background: rgba(30, 41, 59, 1);
        }
        
        .mc-data-table th.sortable::after {
            content: " ⇅";
            opacity: 0.5;
            font-size: 0.75rem;
        }
        
        .mc-data-table th.sort-asc::after {
            content: " ▲";
            opacity: 1;
            color: #3b82f6;
        }
        
        .mc-data-table th.sort-desc::after {
            content: " ▼";
            opacity: 1;
            color: #3b82f6;
        }
        
        .mc-data-table td {
            padding: 0.75rem;
            border-bottom: 1px solid rgba(148, 163, 184, 0.1);
            color: #cbd5e1;
        }
        
        .mc-data-table tr:hover td {
            background: rgba(30, 41, 59, 0.4);
        }
        
        .mc-data-table tr.selected td {
            background: rgba(59, 130, 246, 0.15);
        }
        
        .mc-table-filter {
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(148, 163, 184, 0.2);
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1rem;
        }
        
        .mc-pagination {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 0.5rem;
            margin-top: 1rem;
            padding: 0.75rem;
        }
        
        .mc-page-btn {
            min-width: 36px;
            height: 36px;
            border-radius: 6px;
            border: 1px solid rgba(148, 163, 184, 0.2);
            background: rgba(15, 23, 42, 0.6);
            color: #94a3b8;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .mc-page-btn:hover {
            background: rgba(30, 41, 59, 0.8);
            color: #f1f5f9;
        }
        
        .mc-page-btn.active {
            background: #3b82f6;
            color: white;
            border-color: #3b82f6;
        }
        
        .mc-page-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        /* Checkbox personalizado */
        .mc-table-checkbox {
            width: 18px;
            height: 18px;
            cursor: pointer;
        }
        </style>
        """, unsafe_allow_html=True)
    
    def _render_filters(self):
        """Renderizar controles de filtro."""
        with st.expander("🔍 Filtros", expanded=False):
            cols = st.columns(min(len(self.columns), 4))
            
            for i, col in enumerate(self.columns):
                if not col.filterable:
                    continue
                
                with cols[i % 4]:
                    filter_key = f"{self._filters_key}_{col.key}"
                    current_value = st.session_state.get(filter_key, "")
                    
                    new_value = st.text_input(
                        col.label,
                        value=current_value,
                        key=filter_key,
                        placeholder=f"Filtrar {col.label}...",
                    )
    
    def _apply_filters(self) -> List[Dict[str, Any]]:
        """Aplicar filtros a los datos."""
        filtered = self.data.copy()
        
        for col in self.columns:
            if not col.filterable:
                continue
            
            filter_key = f"{self._filters_key}_{col.key}"
            filter_value = st.session_state.get(filter_key, "").strip().lower()
            
            if filter_value:
                filtered = [
                    row for row in filtered
                    if filter_value in str(row.get(col.key, "")).lower()
                ]
        
        return filtered
    
    def _apply_sorting(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Aplicar ordenamiento a los datos."""
        sort_col = st.session_state.get(self._sort_key)
        sort_order = st.session_state.get(self._sort_order_key, "asc")
        
        if not sort_col:
            return data
        
        reverse = sort_order == "desc"
        
        try:
            # Intentar ordenar como número
            return sorted(data, key=lambda x: float(x.get(sort_col, 0) or 0), reverse=reverse)
        except (ValueError, TypeError):
            # Ordenar como string
            return sorted(data, key=lambda x: str(x.get(sort_col, "")).lower(), reverse=reverse)
    
    def _apply_pagination(self, data: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
        """Aplicar paginación."""
        total_pages = max(1, (len(data) + self.rows_per_page - 1) // self.rows_per_page)
        
        current_page = st.session_state.get(self._page_key, 0)
        current_page = max(0, min(current_page, total_pages - 1))
        
        start = current_page * self.rows_per_page
        end = start + self.rows_per_page
        
        return data[start:end], total_pages
    
    def _render_table_header(self):
        """Renderizar header de la tabla."""
        # Usar columnas de Streamlit para el header
        header_cols = st.columns([1 if col.width else 3 for col in self.columns])
        
        for i, col in enumerate(self.columns):
            with header_cols[i]:
                sort_indicator = ""
                current_sort = st.session_state.get(self._sort_key)
                current_order = st.session_state.get(self._sort_order_key, "asc")
                
                if current_sort == col.key:
                    sort_indicator = " ▲" if current_order == "asc" else " ▼"
                elif col.sortable:
                    sort_indicator = " ⇅"
                
                label = f"{col.label}{sort_indicator}"
                
                if col.sortable:
                    if st.button(label, key=f"{self.key}_sort_{col.key}", use_container_width=True):
                        if current_sort == col.key:
                            # Toggle order
                            new_order = "desc" if current_order == "asc" else "asc"
                            st.session_state[self._sort_order_key] = new_order
                        else:
                            st.session_state[self._sort_key] = col.key
                            st.session_state[self._sort_order_key] = "asc"
                        st.rerun()
                else:
                    st.caption(label)
    
    def _render_table_rows(self, data: List[Dict[str, Any]], enable_selection: bool):
        """Renderizar filas de la tabla."""
        for row_idx, row in enumerate(data):
            row_cols = st.columns([1 if col.width else 3 for col in self.columns])
            
            for col_idx, col in enumerate(self.columns):
                with row_cols[col_idx]:
                    value = row.get(col.key, "")
                    
                    # Aplicar formatter si existe
                    if col.formatter:
                        value = col.formatter(value)
                    
                    # Alineación
                    align_style = f"text-align: {col.align};"
                    
                    st.markdown(f"""
                    <div style="{align_style} padding: 0.5rem 0; color: #cbd5e1;">
                        {html.escape(str(value))}
                    </div>
                    """, unsafe_allow_html=True)
            
            # Separador
            st.markdown("<hr style='margin: 0.25rem 0; opacity: 0.2;'>", unsafe_allow_html=True)
    
    def _render_pagination_controls(self, total_pages: int):
        """Renderizar controles de paginación."""
        current_page = st.session_state.get(self._page_key, 0)
        
        cols = st.columns([1, 3, 1])
        
        with cols[0]:
            if st.button("⬅️ Anterior", disabled=current_page == 0):
                st.session_state[self._page_key] = current_page - 1
                st.rerun()
        
        with cols[1]:
            st.markdown(f"""
            <div style="text-align: center; color: #94a3b8; padding: 0.5rem;">
                Página {current_page + 1} de {total_pages}
            </div>
            """, unsafe_allow_html=True)
        
        with cols[2]:
            if st.button("Siguiente ➡️", disabled=current_page >= total_pages - 1):
                st.session_state[self._page_key] = current_page + 1
                st.rerun()
    
    def _get_selected(self) -> List[str]:
        """Obtener IDs de filas seleccionadas."""
        return st.session_state.get(self._selected_key, [])


# ============================================================
# FUNCIONES DE EXPORTACIÓN
# ============================================================

def export_to_excel(
    data: List[Dict[str, Any]],
    filename: str = "export.xlsx",
    columns: Optional[List[str]] = None,
) -> bytes:
    """
    Exportar datos a Excel.
    
    Returns:
        Bytes del archivo Excel
    """
    df = pd.DataFrame(data)
    
    if columns:
        df = df[columns]
    
    # Crear buffer
    import io
    buffer = io.BytesIO()
    
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Datos')
        
        # Auto-ajustar columnas
        worksheet = writer.sheets['Datos']
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    return buffer.getvalue()


def export_to_csv(
    data: List[Dict[str, Any]],
    filename: str = "export.csv",
    columns: Optional[List[str]] = None,
) -> str:
    """
    Exportar datos a CSV.
    
    Returns:
        String CSV
    """
    df = pd.DataFrame(data)
    
    if columns:
        df = df[columns]
    
    return df.to_csv(index=False)


def render_export_buttons(
    data: List[Dict[str, Any]],
    columns: Optional[List[str]] = None,
    filename_prefix: str = "medicare_export",
    key: str = "export",
):
    """
    Renderizar botones de exportación.
    """
    cols = st.columns(3)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    
    with cols[0]:
        excel_data = export_to_excel(data, f"{filename_prefix}_{timestamp}.xlsx", columns)
        st.download_button(
            label="📊 Excel",
            data=excel_data,
            file_name=f"{filename_prefix}_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{key}_excel",
            use_container_width=True,
        )
    
    with cols[1]:
        csv_data = export_to_csv(data, f"{filename_prefix}_{timestamp}.csv", columns)
        st.download_button(
            label="📄 CSV",
            data=csv_data,
            file_name=f"{filename_prefix}_{timestamp}.csv",
            mime="text/csv",
            key=f"{key}_csv",
            use_container_width=True,
        )
    
    with cols[2]:
        # JSON
        import json
        json_data = json.dumps(data, indent=2, default=str)
        st.download_button(
            label="🗄️ JSON",
            data=json_data,
            file_name=f"{filename_prefix}_{timestamp}.json",
            mime="application/json",
            key=f"{key}_json",
            use_container_width=True,
        )


# ============================================================
# TABLA PREDEFINIDA PARA PACIENTES
# ============================================================

def create_pacientes_table(
    pacientes: List[Dict[str, Any]],
    key: str = "pacientes_table",
) -> DataTable:
    """
    Crear tabla predefinida para listado de pacientes.
    
    Args:
        pacientes: Lista de diccionarios con datos de pacientes
        key: Clave única para la tabla
    
    Returns:
        DataTable configurada
    """
    columns = [
        TableColumn("nombre_completo", "Nombre", width="30%"),
        TableColumn("dni", "DNI", width="15%", align="center"),
        TableColumn("obra_social", "Obra Social", width="20%"),
        TableColumn("estado", "Estado", width="15%", align="center",
                    formatter=lambda x: f"<span class='mc-badge mc-badge-{'success' if x == 'Activo' else 'info'}'>{x}</span>"),
        TableColumn("telefono", "Teléfono", width="20%", align="center"),
    ]
    
    return DataTable(pacientes, columns, key, rows_per_page=15)


# ============================================================
# DEMO
# ============================================================

def demo_data_tables():
    """Demo interactiva de las tablas mejoradas."""
    st.markdown("## 📊 Tablas de Datos Mejoradas")
    
    # Datos de ejemplo
    sample_data = [
        {"id": "1", "nombre_completo": "María González", "dni": "28.456.123", 
         "obra_social": "OSDE", "estado": "Activo", "telefono": "11-4567-8901",
         "edad": 45, "ultima_visita": "2026-04-20"},
        {"id": "2", "nombre_completo": "Juan Pérez", "dni": "25.678.901", 
         "obra_social": "Swiss Medical", "estado": "Internado", "telefono": "11-5678-9012",
         "edad": 62, "ultima_visita": "2026-04-22"},
        {"id": "3", "nombre_completo": "Ana Rodríguez", "dni": "31.234.567", 
         "obra_social": "Galeno", "estado": "Activo", "telefono": "11-6789-0123",
         "edad": 34, "ultima_visita": "2026-04-18"},
        {"id": "4", "nombre_completo": "Carlos Martínez", "dni": "19.876.543", 
         "obra_social": "OSDE", "estado": "Alta", "telefono": "11-7890-1234",
         "edad": 78, "ultima_visita": "2026-04-15"},
        {"id": "5", "nombre_completo": "Laura Silva", "dni": "32.109.876", 
         "obra_social": "Medicus", "estado": "Activo", "telefono": "11-8901-2345",
         "edad": 28, "ultima_visita": "2026-04-21"},
    ] * 3  # Multiplicar para tener más datos
    
    # Crear tabla
    table = create_pacientes_table(sample_data, key="demo_pacientes")
    
    # Renderizar
    st.markdown("### Tabla de Pacientes")
    table.render(enable_selection=False)
    
    # Exportar
    st.markdown("---")
    st.markdown("### 📥 Exportar Datos")
    render_export_buttons(sample_data, filename_prefix="pacientes_demo")
