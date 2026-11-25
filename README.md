# OXEYE · Gestor de trabajo compartido (GitHub Pages)

Mini aplicación web para gestionar y ticar tareas compartidas entre equipo **100% sobre GitHub**, sin servidores externos ni bases de datos aparte.

- **Web estática** servida desde GitHub Pages (`index.html`).
- **Base de datos en el propio repo** (`data/tasks.json`), leída y actualizada en directo mediante la **GitHub REST API**.
- **Sincronización automática** cada 8 segundos (usando `ETag` para no consumir cuota cuando no hay cambios) y al volver a la pestaña.
- **Ticar tareas en 1 clic** directamente desde la tabla (`Trabajo → Por revisar → Historial`) o editarlas con detalle, valoraciones 1–10, comentarios y adjuntos (`data/adjuntos/`).
- **Protección contra conflictos** automática (si ambos editáis a la vez, GitHub avisa en lugar de sobrescribir) + historial completo en Git.

---

## Cómo ponerlo en marcha en 5 minutos

### 1. Crear el repositorio y subir estos archivos
1. Crea un repositorio nuevo en GitHub (por ejemplo `oxeye-tareas`).
   - *Nota:* En cuentas gratuitas de GitHub, GitHub Pages requiere que el repositorio sea **público**. Si quieres que las tareas sean 100% privadas, mira el apartado «Modo privado» más abajo.
2. Sube el contenido de esta carpeta a la rama `main`:
   ```bash
   git init
   git add .
   git commit -m "Inicializar OxEye compartido"
   git branch -M main
   git remote add origin https://github.com/TU_USUARIO/oxeye-tareas.git
   git push -u origin main
   ```
3. Invita a tu colega como **colaborador** en el repositorio:  
   `Settings → Collaborators → Add people`.

### 2. Activar GitHub Pages
1. Ve a `Settings → Pages` dentro del repositorio.
2. En **Build and deployment**:
   - **Source:** `Deploy from a branch`
   - **Branch:** `main` · carpeta `/ (root)`
3. Pulsa **Save**. En ~1 minuto tendrás tu web activa en:  
   `https://TU_USUARIO.github.io/oxeye-tareas/`

### 3. Crear el Token de acceso (tú y tu colega, una sola vez)
Cada persona entra con su propio **Fine-Grained Personal Access Token** de GitHub:
1. Abre [github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new).
2. Pon un nombre (ej. `OxEye Tareas`) y la caducidad que prefieras.
3. En **Repository access**, elige **Only select repositories** y selecciona vuestro repositorio (`oxeye-tareas`).
4. En **Permissions → Repository permissions**, marca:
   - **Contents:** `Read and write`
5. Pulsa **Generate token** y cópialo.
6. Abre la URL de vuestra GitHub Page, pega el token (el repositorio se detecta solo), elige tu función (`Desarrollo`, `Dirección` o `Revisión`) y entra. El navegador recordará tu sesión.

---

## Modo privado (opcional, sigue siendo 100% GitHub)

Si no quieres que `data/tasks.json` sea visible en un repositorio público:
1. Mantén este repositorio público solo para servir la web (`index.html`, `config.js`).
2. Crea un **segundo repositorio privado** (ej. `TU_USUARIO/oxeye-datos`) e invita a tu colega.
3. Edita `config.js` y cambia la línea `repo`:
   ```js
   repo: 'TU_USUARIO/oxeye-datos',
   ```
4. Genera los tokens dando permiso `Contents: Read and write` sobre `oxeye-datos`. Al entrar por primera vez, la app creará automáticamente `data/tasks.json` dentro del repo privado.

---

## Estructura del proyecto

- `index.html` — Aplicación completa (interfaz + cliente GitHub API).
- `config.js` — Configuración opcional del repositorio, rama, intervalo y roles por usuario de GitHub.
- `data/tasks.json` — Tareas compartidas, comentarios y registro de actividad.
- `data/adjuntos/` — Archivos adjuntos subidos desde las fichas (hasta 5 MB por archivo).
- `.nojekyll` — Evita procesamiento innecesario en GitHub Pages.
- `legacy/` — Copia archivada del antiguo servidor local en Python (`servidor.py`) por si necesitas consultarlo.
