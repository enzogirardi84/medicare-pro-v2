# Configuración de Protección de Rama Principal (Fase 3)

Esta guía documenta cómo configurar reglas de protección para la rama `main` en GitHub.

## Pasos para Configurar Protección de Rama

### 1. Acceder a Configuración de GitHub

1. Ir a: `https://github.com/enzogirardi84/medicare-pro-v2/settings/branches`
2. Click en "Add rule" (Agregar regla)
3. En "Branch name pattern" escribir: `main`

### 2. Configurar Reglas de Protección

Marcar las siguientes opciones:

#### Require a pull request before merging
- ✅ **Require approvals**: Mínimo 1 aprobación
- ✅ **Dismiss stale PR approvals when new commits are pushed**
- ✅ **Require review from CODEOWNERS** (opcional, si hay archivo CODEOWNERS)

#### Require status checks to pass before merging
- ✅ **Require status checks to pass**
  - Buscar y agregar: `medicare-lint / Lint, Format y Security Check`
  - Buscar y agregar: `medicare-lint / Type Checking básico`

#### Require conversation resolution before merging
- ✅ **Require conversation resolution** (todos los comentarios resueltos)

#### Require signed commits
- ⬜ Opcional: Requerir commits firmados GPG

#### Include administrators
- ✅ **Include administrators** (las reglas aplican también a admins)

#### Restrict who can push to matching branches
- ✅ **Restrict pushes that create files larger than 100 MB**
- ✅ **Allow force pushes**: NO (desmarcar)
- ✅ **Allow deletions**: NO (desmarcar)

### 3. Configuración Adicional (Settings)

Ir a `https://github.com/enzogirardi84/medicare-pro-v2/settings`:

#### General > Pull Requests
- ✅ **Allow merge commits** (mantener historial)
- ✅ **Allow squash merging** (opcional)
- ✅ **Allow rebase merging** (opcional)
- ✅ **Automatically delete head branches** (limpieza automática)

#### Security > Secret scanning
- ✅ **Secret scanning**: Habilitar
- ✅ **Push protection**: Habilitar (evita pushes con secrets)

#### Code and automation > GitHub Actions > General
- ✅ **Allow all actions and reusable workflows**
- ✅ **Require approval for first-time contributors**

### 4. Variables de Entorno (Secrets)

Verificar que NO estén hardcodeadas en el código. Ir a:
`https://github.com/enzogirardi84/medicare-pro-v2/settings/secrets/actions`

Secrets requeridos:
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `AUDIT_SECRET_KEY`
- `ENCRYPTION_KEY` (si aplica)

NO deben estar en:
- ✅ Archivos de código
- ✅ Commits
- ✅ `.env.example` (verificar que no tenga valores reales)

### 5. Auditoría de Secrets

Ejecutar localmente para verificar:

```bash
# Buscar posibles secrets hardcodeados
grep -r "password\|secret\|key\|token" --include="*.py" . | grep -v ".pyc" | grep -v "__pycache__"

# Usar herramienta de escaneo
git log --all --full-history --source -- '*.py' | grep -i "password\|secret\|key"
```

## Workflow de Desarrollo Recomendado

```
1. Crear feature branch: git checkout -b codex/nueva-funcionalidad
2. Desarrollar y commitear cambios
3. Push a GitHub: git push origin codex/nueva-funcionalidad
4. Crear Pull Request a `main`
5. Esperar que pasen los checks (linting, tests)
6. Revisión de código (code review)
7. Merge via GitHub (no push directo a main)
```

## Comandos Útiles

```bash
# Verificar estado de protección
curl -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/enzogirardi84/medicare-pro-v2/branches/main/protection

# Listar reglas de rama
curl -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/enzogirardi84/medicare-pro-v2/rules/branches/main
```

## Referencias

- [GitHub Docs - About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [GitHub Docs - Managing a branch protection rule](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule)
