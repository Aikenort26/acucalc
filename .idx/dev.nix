# .idx/dev.nix — Configuración de Google Project IDX para ACUCALC v7
# Configura Python 3.11, instala dependencias automáticamente
# y lanza Streamlit como preview web.
{ pkgs, ... }: {
  channel = "stable-23.11";

  # Paquetes del sistema necesarios
  packages = [
    pkgs.python311
    pkgs.python311Packages.pip
    pkgs.gnumake
  ];

  # Integraciones de IDX
  idx = {
    extensions = [
      "ms-python.python"
    ];

    # Inicialización automática del workspace
    workspace = {
      onCreate = {
        setup-venv = ''
          python3 -m venv .venv
          source .venv/bin/activate
          pip install --upgrade pip
          pip install -r requirements.txt
        '';
      };
      onStart = {
        activate = ''
          source .venv/bin/activate
        '';
      };
    };

    # Vista previa de Streamlit — usa app.py como entry point
    previews = {
      enable = true;
      previews = {
        web = {
          command = [
            "./.venv/bin/streamlit"
            "run"
            "app.py"
            "--server.port"
            "$PORT"
            "--server.address"
            "0.0.0.0"
            "--server.headless"
            "true"
            "--server.fileWatcherType"
            "none"
          ];
          manager = "web";
        };
      };
    };
  };
}
