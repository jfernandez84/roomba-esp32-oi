# Fase 1: instalar el Jetson Nano Developer Kit

Guía para el **Jetson Nano Developer Kit original (P3450)** con un Mac. Se basa en la [guía oficial de NVIDIA](https://developer.nvidia.com/embedded/learn/get-started-jetson-nano-devkit). Los pasos todavía no se han hecho en mi placa: se irán marcando.

## Lo que necesitas

- **Tarjeta microSD:** NVIDIA recomienda 32 GB UHS-1 como mínimo. Para este proyecto (ROS, contenedores, modelos) conviene 64 GB o más.
- **Fuente de alimentación de 5 V**, con una de estas dos opciones:
  - **Micro-USB 5 V / 2 A.** NVIDIA avisa de que muchas fuentes etiquetadas "2 A" no los dan de verdad. Es la opción más justa.
  - **Conector cilíndrico 5 V / 4 A** (la placa lo marca "5V MAX 4A") con un puente (jumper) en **J48**. Es lo recomendable si se van a conectar periféricos o a cargar el sistema.
- Monitor con HDMI o DisplayPort (los adaptadores HDMI-DVI no están soportados), teclado y ratón USB.
- Un Mac con internet y lector de microSD.

### Aviso importante sobre la alimentación

**No conectes el adaptador de 12 V del Roomba al Jetson.** El conector cilíndrico del Jetson es de **5 V**; con 12 V se daña. Usa una fuente de 5 V propia.

En la foto de mi placa, J48 está sin puente. Con J48 sin puente, el Jetson se alimenta por el micro-USB.

## 1. Descargar la imagen

Desde la guía de NVIDIA, descarga la imagen **"Jetson Nano Developer Kit SD Card Image"** (un archivo `.zip` de varios gigabytes). La página que consulté no indica el número de JetPack, así que comprueba el nombre del archivo al descargarlo. Según NVIDIA, la última serie para el Nano es JetPack 4.6.x.

## 2. Grabar la tarjeta (en el Mac)

Con **balenaEtcher**:
1. Abre Etcher, elige el `.zip` sin descomprimir, elige la microSD y pulsa *Flash*.
2. Espera a que verifique.

(La alternativa es `diskutil` y `dd` por Terminal, pero escribe directamente en un dispositivo de disco: hay que identificar bien cuál es antes de ejecutarlo. Lo normal es usar Etcher.)

## 3. Primer arranque con monitor

1. Inserta la microSD en la ranura de la **parte inferior del módulo** (bajo el disipador).
2. Conecta monitor, teclado y ratón.
3. Conecta la alimentación. Un LED verde junto al conector micro-USB indica que hay corriente, y la placa arranca sola.
4. Sigue el asistente: acepta la licencia, elige idioma, teclado y zona horaria, y crea usuario, contraseña y nombre del equipo. Para el tamaño de la partición APP, NVIDIA recomienda el máximo.

## 4. Comprobado tras el primer arranque

- Arranca y responde en la red local (ping sin pérdidas, puerto 22 abierto).
- `cat /etc/nv_tegra_release` da **R32 revisión 7.1** (L4T 32.7.1), que corresponde a **JetPack 4.6.1** con Ubuntu 18.04 (la correspondencia es de mi memoria).
- Acceso por SSH con `ssh <usuario>@<ip>` desde el Mac.

## 5. Después del primer arranque

1. **Actualizar el sistema:** `sudo apt update && sudo apt upgrade`. **No** ejecutes `do-release-upgrade` ni subas a Ubuntu 20.04: el Nano no lo soporta y se pierde la compatibilidad con los controladores de NVIDIA.
2. **Entrar sin contraseña** desde el Mac con una clave SSH (`ssh-keygen` y `ssh-copy-id`).
3. **Modo de energía y temperatura:** `sudo nvpmodel -q` y `tegrastats`.
4. **Herramientas básicas:** Python 3, pip, git, `python3-serial`, `nano`.

## Refrigeración

El disipador del kit es pasivo. La placa tiene un conector de ventilador (**J15**), por si se hace trabajo pesado durante mucho tiempo. Confirma el tipo de ventilador que acepta antes de comprar uno.
