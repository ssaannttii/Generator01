# Estudio integral para generador de "star charts"

Este documento describe el objetivo visual, la arquitectura recomendada, el pipeline de producción y los algoritmos clave para crear un generador de **star charts** con acabado profesional idéntico a la referencia: anillos concéntricos, UI diegética tipo HUD y núcleo estelar con bloom y aberración cromática controlados.

---

## 1. Objetivo visual ("calidad objetivo")

- **Composición**: vista 3D con perspectiva oblicua; anillos concéntricos (paleta rojo/azul), núcleo denso de estrellas en el centro, labels curvados y *ticks* radiales.
- **Estética**: "neón técnico" (azules eléctricos, rojos anaranjados, acentos ámbar) sobre fondo negro puro.
- **Post**: bloom intenso para altas luces, *glow* aditivo en líneas, aberración cromática sutil, *vignette* ligero, *film grain* y posibles *chromatic streaks* en estrellas brillantes.
- **Tipografía/UI**: dígitos tabulares, kerning apretado, iconografía fina de inspiración astronómica, texto curvado a lo largo de arcos.
- **Legibilidad**: labels sin colisiones, contraste mínimo 7:1 frente al fondo, halos sin invadir texto.

### Criterios de aceptación (pruebas de "igual estilo")

- Densidad de estrellas decreciente con la distancia radial (ley de potencia) y ≥ 3 tamaños de *bokeh*.
- Líneas con doble trazo (core nítido + halo difuso) y blending realmente aditivo.
- Aberración cromática radial ≤ 2 px a 4K; bloom con *threshold* alto (solo luces > 1.0 en HDR).
- Texto curvado sin escalonado a 8K; dígitos alineados (tabulares).
- Exporte a 16-bit (TIFF/EXR) y PNG 8-bit con *tonemapping* ACES o equivalente.

---

## 2. Arquitecturas viables

| Opción | Qué aporta | Pros | Contras | Cuándo elegir |
| --- | --- | --- | --- | --- |
| **Blender + Python (headless, Eevee/Compositor)** | Geometría 3D para anillos y estrellas como *billboards*, postprocesado cinematográfico | Bloom/Glare, aberración y DOF nativos; texto sobre curvas; renders 8–16K offline | Curva de aprendizaje de scripting; tipografía SDF opcional | **Recomendado** para máxima fidelidad y control del post sin reinventar shaders |
| **Python + OpenGL (moderngl/vispy) + shaders** | Motor 2D/3D propio | Control total del *pipeline* y rendimiento | Implementar SDF fonts, bloom multipaso, CA y layout curvo | Cuando se necesita un motor ligero, reproducible y 100% propio |
| **WebGL/Three.js** | Render interactivo web | Portabilidad y fácil compartición | Tipografía y *post* a medida; límites de RAM para 8K | Prioridad web/tiempo real |
| **Unity/Unreal** | Tiempo real con *post* AAA | Perfilado y *post* maduros | Tooling más pesado; licencias | Si se buscan escenas interactivas o vídeo |

> **Recomendación**: Blender + Python en modo headless para *stills* ultra nítidos. Complementar con un motor secundario en moderngl si se desea un modo paramétrico en tiempo real.

---

## 3. Pipeline de render (capas)

1. **Layout paramétrico (CPU)**
   - Sistema de coordenadas polares 3D (anillos como toros planos o discos finos).
   - Generación de anillos: radio, grosor, color, patrones de *dash*, *ticks* y subdivisiones.
   - Etiquetado radial: posición por arco y orientación tangente; resolución de colisiones (ver § Algoritmos).
   - Iconos y *glyphs* anclados a anillos o estrellas.
2. **Campo estelar (GPU)**
   - Distribución mixta: núcleo (gaussiana 2D o ley de Sérsic) + halo (Poisson o *blue-noise*).
   - Magnitud → tamaño y color (mapa temperatura-color opcional).
   - Render como *point sprites* con *falloff* gaussiano y blending aditivo.
3. **UI vectorial**
   - Trazos dobles: core nítido + *outer glow* (segunda pasada con *blur* gaussiano).
   - Texto sobre curvas mediante SDF o mallas convertidas a *billboards*.
4. **Postprocesado HDR**
   - *Bloom* umbralado multipaso (downsample, blur, upsample).
   - Aberración cromática radial: desplazamiento por canal ~k·r².
   - Vignette, grano, leve *lens distortion* y tonemapping (ACES/Filmic).
   - Control final mediante LUT para asegurar paleta y contraste.

---

## 4. Algoritmos clave

### 4.1 Distribución de estrellas

- Núcleo: densidad \(\rho(r) = \rho_0 \cdot e^{-(r/\sigma)^\alpha}\) (Sérsic simplificado, \(\alpha\) ≈ 2–4).
- Halo: muestreo *blue-noise* o Poisson con rechazo para evitar clustering indeseado.
- Brillo: magnitud con ley de potencia \(P(s) \propto s^{-\gamma}\), \(\gamma \in [1.5, 2.5]\); *clamp* y *bias* para unas pocas estrellas muy brillantes.
- Color: rampa fría-cálida comprimida (evitar verdes).

### 4.2 Anillos y marcas

- Generar *paths* con muestreo uniforme por arco-longitud para colocar *ticks*.
- Patrones de *dash* y etiquetas en subdivisiones lógicas (p. ej. cada N unidades).

### 4.3 Layout de etiquetas (colisión cero)

- Modelo: cada label es un arco \([\theta_1, \theta_2]\) y una *bounding box* proyectada.
- Estrategia: colocación inicial por importancia (más largos o brillantes primero) y separación por fuerzas angulares de repulsión hasta anular superposiciones. En caso límite, usar *leader lines* a arcos auxiliares.
- Microtipografía: tracking negativo leve en mayúsculas, dígitos tabulares, hinting desactivado si se usan SDF.

### 4.4 Post

- Bloom: 4–6 niveles, *threshold* ≈ 1.0–1.2 en espacio lineal, intensidad global < 0.4; clamp por capa para que el texto no se lave.
- Aberración cromática: desplazamiento por canal \(= k\cdot r^2\) con mezcla → 0 en el centro.
- Grano: gaussiano o *blue-noise* en espacio log, σ bajo para evitar bandas.

---

## 5. Parámetros del generador (expuestos al usuario)

- **Semilla** RNG.
- **Resolución** y factor SSAA.
- **Anillos**: número, radios, grosores, colores, *dash*, opacidad, radio del *glow*.
- **Estrellas**: cuenta total, σ/α del núcleo, γ de brillo, tamaño mínimo/máximo, rampa de color.
- **Etiquetas**: fuentes, tamaños, *arc padding*, reglas anti-colisión, *leader lines* (on/off).
- **Cámara**: inclinación, FOV, *tilt-shift*, DOF on/off.
- **Post**: threshold/intensidad de bloom, aberración cromática, vignette, LUT.
- **Exportes**: PNG 8-bit, TIFF/EXR 16-bit, PSD por capas (UI/estrellas/post).

### Formato de escena sugerido (YAML)

```yaml
seed: 2411
resolution: {width: 4096, height: 6144, ssaa: 2}
camera: {tilt_deg: 35, fov_deg: 35}
rings:
  - {r: 0.35, width: 0.006, color: "#1E90FF", dash: [8, 3], ticks_every_deg: 10, label: "20.64 Mσ"}
  - {r: 0.42, width: 0.006, color: "#FF3B2F", dash: [10, 4]}
stars:
  core: {sigma: 0.18, alpha: 3.2, count: 18000}
  halo: {count: 6000, min_r: 0.35, max_r: 1.0}
  brightness_power: 1.9
text:
  font: "Orbitron"
  size_px: 26
  tabular_digits: true
post:
  bloom: {threshold: 1.1, intensity: 0.32}
  chromatic_aberration: {k: 0.002}
  vignette: 0.12
  lut: "neo_sciFi.cube"
```

---

## 6. Tipografía, iconografía y color

- **Fuentes libres**: Orbitron, Michroma, Antonio, Rajdhani (peso medio). Usar dígitos tabulares; si no están disponibles, hornear MSDF propios para números.
- **Iconografía**: set en SVG con trazo único para mantener la alineación de strokes.
- **Paleta**:
  - Azules: `#1E90FF`, `#00B5FF`
  - Rojos-naranja: `#FF3B2F`, `#FF6A00`
  - Acento ámbar: `#FFC107`
- Sellar la paleta con un LUT final para consistencia entre escenas.

---

## 7. Datos de entrada posibles

- **Procedural**: máxima flexibilidad y estilo puro.
- **Catálogos reales** (Gaia/SDSS): mapear distancia a anillos (bins logarítmicos). Requiere *decimation* y normalización de magnitudes para mantener estética (revisar licencias y atribuciones al distribuir).

---

## 8. Exportación y producción

- Render principal en EXR/TIFF 16-bit lineal; aplicar tonemap y derivar PNG.
- Opción de PSD por capas: `stars`, `ui-core`, `ui-glow`, `post` para retoques.
- Presets de calidad: 4K, 8K, póster (300 ppp).

---

## 9. Validación de calidad

- **Automática**: SSIM/LPIPS vs *golden frames* por preset; histograma de luminancia (picos controlados) y porcentaje de píxeles > 0.95 (evitar *clipping*).
- **Checklist visual**:
  - Texto legible al 50% de zoom en 4K.
  - Ningún label interfiere con otra entidad.
  - Halos no desaturan los colores de UI.
  - Núcleo con gradiente suave, sin *banding* (dithering activo).

---

## 10. Riesgos y mitigación

- **Texto borroso a 8K** → usar SDF/MSDF y desactivar hinting; renderizar a 2× y hacer *downsample* (SSAA).
- **Bloom que lava el texto** → separar UI en capa sin bloom o usar *bloom mask* por material.
- **Banding** en gradientes → 16-bit + grano fino + *error diffusion dithering*.
- **Colisiones persistentes** → *leader lines* automáticos y priorización de etiquetas críticas.

---

## 11. Plan de desarrollo (fases y entregables)

1. **Especificación visual y presets**: definir LUT, paleta, tipografías y 3 "golden frames" (núcleo denso, medio, disperso).
2. **Core de layout**: generación de anillos, *ticks* y parámetros; escena YAML/JSON.
3. **Campo estelar**: núcleo + halo, brillo/tamaño/temperatura, control por semilla.
4. **Texto curvo y colisiones**: motor de etiquetas con fuerzas/recocido y *leader lines*.
5. **Postprocesado HDR**: bloom multipaso, CA radial, LUT, grano, vignette; *masking* por capas.
6. **Exportes y QA**: render 4K/8K 16-bit, PSD por capas, pruebas SSIM/LPIPS y checklist.
7. **UI del generador (CLI/GUI)**: carga/edición de presets, reproducibilidad por semilla.

---

## 12. Notas de implementación (Blender + Python)

- Escena: discos extruidos mínimos para anillos (material emisivo para el *glow*), cámara inclinada 25–40° con FOV 30–40°.
- Estrellas: sistema de partículas con *billboards* emisivos o *Geometry Nodes* para distribuir puntos.
- Texto: objetos de Texto seguidos a Curvas; convertir a malla solo si se requiere SDF propio.
- Post: usar bloom de Eevee y el Compositor (Glare, Lens Distortion, Vignette, Film Grain simulado).
- Headless: lanzar renders por CLI y construir la escena desde YAML.

---

## 13. Notas de implementación (Python + OpenGL)

- Render a FBO 16-bit con SSAA 2×–4×.
- Shaders:
  - *Point sprites* gaussianos para estrellas con blending aditivo.
  - Pasada UI: líneas con halo (dos *draw calls*).
  - MSDF para texto (fuente prehorneada).
  - Post en *ping-pong*: bloom → aberración cromática → vignette → LUT.
- Texto curvo: colocar *glyph quads* siguiendo la tangente del camino (suma de *advances*) con ajuste de kerning.

---

## 14. Próximos pasos sugeridos

Preparar:

- Tres presets de escena (denso, medio, disperso).
- Esquema de materiales/post exactos.
- Lista de fuentes e iconos a incluir en el repositorio.

