# ARBA IBPER Contable

## Uso en servidores (recomendado)

Copiá la carpeta portable completa:

`app/portable/ARBA_IBPER`

En el servidor ejecutá `Iniciar.bat` (o `ARBA_IBPER.exe`).

**No requiere instalar Python.**

Si necesitás regenerar el portable en una PC de desarrollo:

```bat
cd app
build_portable.bat
```

## SQL

- Misma lógica que `txtARBA_Contable`
- `VW_ImpuestosReg2 WITH (NOLOCK)`
- `SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED`
- Backend por defecto: `pymssql` (no pide ODBC instalado)

Config en `.env` junto al ejecutable.
