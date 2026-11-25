# OXEYE · Gestión del equipo

**Versión 1.0 — Lista de tareas compartida.** Sustituye la sección «06 · Administración y tareas» de la maqueta anterior. No incluye mapa ni simulación. Recupera las 24 tareas existentes y permite añadir otras.

## 1. Ponerlo en marcha

Requiere **Python 3.9 o posterior**. No hay bibliotecas externas que instalar.

**Windows:** descomprime el ZIP y haz doble clic en `INICIAR_WINDOWS.bat`.

**Mac/Linux:** abre Terminal dentro de la carpeta y ejecuta `python3 servidor.py --host 0.0.0.0 --port 8765` (o `./iniciar_mac_linux.sh`).

En el ordenador que aloja la aplicación, abre **http://localhost:8765**. La primera vez se genera el usuario `admin` y una contraseña, que encontrarás en `datos/ACCESO_INICIAL.txt` y en la consola del servidor. Entra y **cambia la contraseña** en el menú de tu cuenta (`···`).

## 2. Que todos vean lo mismo

El equipo debe abrir **la misma dirección del ordenador que ejecuta el servidor**, no copias separadas del HTML. Dentro de la misma red local:

1. Mantén abierto el servidor en el ordenador principal.
2. En ese ordenador, consulta su dirección IPv4 local. En Windows, abre `cmd` y ejecuta `ipconfig`. Busca `Dirección IPv4`, por ejemplo `192.168.1.25`.
3. Desde los demás ordenadores, abre `http://192.168.1.25:8765` sustituyendo la IP por la real. Puede ser necesario permitir el acceso a Python en el cortafuegos de Windows.
4. Desde la cuenta de Dirección, usa `··· → Dar acceso a otra persona` para crear un usuario de Desarrollo o Revisión. Comparte sus credenciales de forma segura.

Las tareas, comentarios y archivos se guardan en **el servidor**, en la carpeta `datos/`. Las pantallas consultan cambios automáticamente cada **2,5 segundos**. No es necesario actualizar manualmente la página.

**Importante:** la sincronización requiere que ese servidor esté encendido y accesible. Si trabajáis desde redes distintas, necesitaréis publicar la aplicación en un servidor privado protegido con **HTTPS** y configurar correctamente el acceso. **No abras el puerto 8765 directamente a Internet**: este paquete está diseñado para equipo de confianza y red controlada, no es una instalación pública endurecida. Un archivo HTML abierto por sí solo no puede sincronizar varias máquinas.

## 3. Uso de la lista

Tres estados:

- **Trabajo:** nuevas features y fixes. Se pueden editar, comentar, adjuntar documentos, asignar y copiar en formato TXT para pasar a los programadores.
- **Pendiente de revisión:** cuando Desarrollo termina, pulsa `Trabajo terminado → Revisión`. No se da por aprobado todavía.
- **Historial de cambios:** Dirección o quien tenga función de Revisión comprueba el criterio de aceptación y valida el trabajo; queda registrado. También se puede devolver a Trabajo si necesita correcciones.

Cada nota registra: **tipo Feature/Fix**, título, descripción, motivo, prueba de aceptación, prioridad, responsable, relaciones y tres puntuaciones diferentes:

- Molestia para la dirección (1–10).
- Dificultad prevista por dirección (1–10).
- Dificultad estimada por el programador (1–10), con su respuesta escrita.

Las 24 tareas importadas tienen inicialmente las puntuaciones **sin valorar**: el programa no inventa esos números. Puedes ponerlos al revisar las fichas.

## 4. Adjuntos y comentarios

Al abrir una tarea, baja hasta `Archivos compartidos`: sube archivos desde tu PC, uno por vez, hasta 15 MB. Otro miembro podrá descargarlos desde la misma ficha, incluso desde otro ordenador. Para añadir archivos mientras editas una ficha, guarda primero los cambios de texto.

Los archivos están en `datos/adjuntos/`. Se admiten documentos, imágenes, ZIP y algunos formatos técnicos. No se ejecutan archivos en el navegador.

## 5. Guardado, conflictos y copias

- Los cambios confirmados se guardan en la base de datos SQLite del servidor.
- Si dos personas modifican la misma ficha al mismo tiempo, el programa bloquea la segunda escritura obsoleta y avisa; **no sobrescribe silenciosamente** los cambios más recientes.
- Para respaldar absolutamente todo, **copia la carpeta `datos/` completa** (preferiblemente con el servidor detenido). Incluye la base de datos, los archivos y las cuentas. Protege esa copia, ya que contiene información de acceso.
- `Exportar JSON` descarga un JSON con las tareas y su historial de conversación, **pero no incorpora los bytes de los adjuntos**; para éstos hay que respaldar `datos/`.
- Si mueves la carpeta completa a otro equipo, conserva `datos/` o perderás el progreso compartido.
- Para detener el servicio, vuelve a la ventana de la consola y pulsa `Ctrl+C`.

## 6. Roles

**Dirección:** crea cuentas, edita trabajo, envía a revisión y valida para el historial.

**Desarrollo:** crea, edita y responde; puede enviar trabajo a revisión o devolver tareas, pero no certificar su aceptación final.

**Revisión:** comparte capacidades de edición y además puede aprobar revisiones para el historial.

La auditoría identifica al usuario autenticado, no sólo al navegador. Guarda las claves de cada usuario de forma privada.

## 7. Limitaciones reconocidas

Esta versión ofrece un **gestor real compartido en la red**, no una conexión desplegada a Internet ni una integración con el repositorio OxEye. No sincroniza con GitHub, Milanote u otros gestores salvo que se desarrolle un conector. Para una instalación institucional o accesible desde cualquier lugar serán necesarios alojamiento continuo, TLS/HTTPS, política de copias automatizadas, controles operativos y revisión de seguridad.
