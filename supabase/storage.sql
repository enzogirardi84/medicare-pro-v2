insert into storage.buckets (id, name, public)
values
    ('medicare-estudios', 'medicare-estudios', false),
    ('medicare-firmas', 'medicare-firmas', false),
    ('medicare-legales', 'medicare-legales', false)
on conflict (id) do nothing;

-- Politicas basicas de ejemplo.
-- Ajustar segun autenticacion real antes de produccion.

drop policy if exists "authenticated can view estudios" on storage.objects;
create policy "authenticated can view estudios"
on storage.objects for select
to authenticated
using (bucket_id = 'medicare-estudios');

drop policy if exists "authenticated can upload estudios" on storage.objects;
create policy "authenticated can upload estudios"
on storage.objects for insert
to authenticated
with check (bucket_id = 'medicare-estudios');

drop policy if exists "authenticated can view firmas" on storage.objects;
create policy "authenticated can view firmas"
on storage.objects for select
to authenticated
using (bucket_id = 'medicare-firmas');

drop policy if exists "authenticated can upload firmas" on storage.objects;
create policy "authenticated can upload firmas"
on storage.objects for insert
to authenticated
with check (bucket_id = 'medicare-firmas');

drop policy if exists "authenticated can view legales" on storage.objects;
create policy "authenticated can view legales"
on storage.objects for select
to authenticated
using (bucket_id = 'medicare-legales');

drop policy if exists "authenticated can upload legales" on storage.objects;
create policy "authenticated can upload legales"
on storage.objects for insert
to authenticated
with check (bucket_id = 'medicare-legales');
