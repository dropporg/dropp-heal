# greenlet (and therefore SQLAlchemy's async layer) loads libstdc++ at runtime,
# which is not on the default library path on NixOS. Entering this shell puts it
# there so `just test`, `just upgrade`, and the app itself can reach MySQL.
{ pkgs ? import <nixpkgs> { } }:

pkgs.mkShell {
  packages = [ pkgs.python313 pkgs.just pkgs.docker-compose ];

  LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [ pkgs.stdenv.cc.cc.lib pkgs.zlib ];

  shellHook = ''
    [ -d venv ] || python -m venv venv
    export PATH="$PWD/venv/bin:$PATH"
  '';
}
