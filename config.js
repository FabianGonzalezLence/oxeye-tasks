window.OXEYE_CONFIG = {
  // Déjalo vacío para detectar automáticamente el repositorio cuando se sirva desde GitHub Pages
  // (https://TU_USUARIO.github.io/TU_REPO/).
  // Si prefieres guardar los datos en un repositorio PRIVADO aparte, escribe aquí "TU_USUARIO/oxeye-datos".
  repo: '',

  // Rama donde se guarda data/tasks.json
  branch: 'main',

  // Ruta del archivo JSON de tareas dentro del repositorio
  dataPath: 'data/tasks.json',

  // Carpeta para adjuntos dentro del repositorio
  attachmentsDir: 'data/adjuntos',

  // Intervalo de sincronización automática en milisegundos (usa ETag / 304 para no gastar cuota)
  pollMs: 8000,

  // Opcional: asigna nombre visible y rol por usuario de GitHub (en minúsculas).
  // Roles disponibles: 'admin' (Dirección), 'desarrollo' (Desarrollo), 'revision' (Revisión)
  members: {
    // 'tu-usuario-github': { display_name: 'Fabián', role: 'desarrollo' },
    // 'usuario-de-tu-colega': { display_name: 'Dirección', role: 'admin' }
  }
};
