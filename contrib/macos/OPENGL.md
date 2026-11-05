# Experimental GTK2/Quartz OpenGL build

This variant produces `../dist/PCB-OpenGL.app`. Its bundle identifier is
`local.geda-pcb.OpenGL.Quartz`, its window title includes OpenGL, and its default
profile is `~/Library/Application Support/PCB-OpenGL-Quartz`. It can run beside
the regular GDK `PCB.app`. Export formats and board file formats are unchanged.
The `PCB_BUNDLE_PROFILE` override is available for disposable test profiles.

## Dependencies and build

Use the build tools listed in README.md, a clean source checkout, and Python
3.12 or newer (the private SDK extraction uses the safe tar extraction filter).
GTK2 and GtkGLExt must both target Quartz. The experimental build accepts
private SDK prefixes and does not install or change global libraries.

Two pinned official Homebrew arm64 bottles were used:

| SDK | Bottle SHA256 |
| --- | --- |
| GTK 2.24.33_2 | `50bf4d48f706e87bc7bff60b97ea41bc0ca1d4616390be8fe2781360531244c2` |
| GtkGLExt 1.2.0_4 (Tahoe) | `764e97c887571389641f45ef171ca06af71ac4bc5fcaaff56e85c9d663cad92a` |

The public bottle URLs are respectively:

- `https://ghcr.io/v2/homebrew/core/gtkx/blobs/sha256:50bf4d48f706e87bc7bff60b97ea41bc0ca1d4616390be8fe2781360531244c2`
- `https://ghcr.io/v2/homebrew/core/gtkglext/blobs/sha256:764e97c887571389641f45ef171ca06af71ac4bc5fcaaff56e85c9d663cad92a`

For anonymous registry downloads use `curl --fail -L --header
'Authorization: Bearer QQ==' URL -o FILE`. The GTK registry repository is
`gtkx`, the bottle's extracted directory is `gtk+/2.24.33_2`. SDK preparers verify
the checksums and refuse to overwrite an existing SDK directory.

From the source checkout, after downloading the bottles:

```sh
python3 contrib/macos/scripts/prepare-gtk-sdk.py \
  --bottle /path/to/gtk.bottle.tar.gz --work ../build/deps/gtk-sdk
python3 contrib/macos/scripts/prepare-gtkglext.py \
  --bottle /path/to/gtkglext.bottle.tar.gz \
  --gtk-prefix "$PWD/../build/deps/gtk-sdk/gtk+/2.24.33_2" \
  --work ../build/deps/gtkglext-sdk
python3 contrib/macos/scripts/build-opengl.py \
  --gtk-prefix "$PWD/../build/deps/gtk-sdk/gtk+/2.24.33_2" \
  --gtkglext-prefix "$PWD/../build/deps/gtkglext-sdk/gtkglext/1.2.0_4"
PCB_BUILD_VARIANT=opengl \
PCB_GTK_PREFIX="$PWD/../build/deps/gtk-sdk/gtk+/2.24.33_2" \
python3 contrib/macos/scripts/build-app.py
python3 contrib/macos/scripts/audit-app.py ../dist/PCB-OpenGL.app
```

An existing compatible private GTK2/Quartz SDK can also be supplied, avoiding
a second copy of GTK. The GTK and GtkGLExt SDKs are needed only for building
and compiling test modules. The resulting app includes their libraries,
modules, data and licenses; runtime does not need these SDK directories.

Build outputs use `build/source-opengl`, `build/opengl`, `install/opengl`,
`docs/opengl-build` and `docs/opengl-bundle`. The build refuses to reuse old
source/build/install outputs. It runs the existing C unit tests before install.
The regular GDK build directories and `dist/PCB.app` are separate.

## Quartz renderer adjustments

`0008-quartz-opengl-framebuffer.patch` supplies Apple's GLU callback type and
uses an FBO for `ghid_render_pixmap` on Quartz. GtkGLExt's Quartz GLPixmap
context can be created but has an incomplete framebuffer (error 1286), so
using it directly gives empty DRC preview pictures. The FBO uses RGBA8 and a
packed depth/stencil renderbuffer; pixels are flipped into an ordinary
GdkPixmap, including padded RGB rows and non-square preview sizes.

The patch preserves matrices, viewport, pixel packing, framebuffer binding and
the previous native CGL context. GtkGLExt Quartz's
`gdk_gl_context_get_current()` returns NULL even while its native context is
current, so CGL is used explicitly for context restoration. A failed preview
returns NULL safely and the DRC cell renderer tolerates it. Non-Quartz OpenGL
builds retain their GLPixmap path; the preview centering calculation now uses
the corresponding width and height. The GDK renderer is not changed.

`0009-quartz-native-gl-drawing-area.patch` forces each OpenGL drawing widget
(main board and footprint previews) to have a native Quartz child window before
GtkGLExt realizes its drawable (including its early configure callback), and
synchronizes the native NSView frame with GTK size allocations. Otherwise GTK2 client-side windows resolve to
the top-level NSView and OpenGL overwrites the menus and other controls. The
regression test compares the actual native canvas and OpenGL view, verifies
its dimensions, checks that menu clicks remain outside the GL view before and after resizing,
and saves an AppKit snapshot of the remaining GTK controls. AppKit snapshots
show the GPU canvas as black; its actual board pixels are captured separately
from the OpenGL front buffer.

## Validation

Set `PKG_CONFIG_LIBDIR` to the GtkGLExt and GTK SDK `lib/pkgconfig` directories,
then the Homebrew pkg-config directories (including the macOS SDK metadata),
when compiling the test-only GTK modules. For example on macOS 26:

```sh
export PKG_CONFIG_LIBDIR="$PWD/../build/deps/gtkglext-sdk/gtkglext/1.2.0_4/lib/pkgconfig:$PWD/../build/deps/gtk-sdk/gtk+/2.24.33_2/lib/pkgconfig:/opt/homebrew/lib/pkgconfig:/opt/homebrew/share/pkgconfig:/opt/homebrew/opt/libffi/lib/pkgconfig:/opt/homebrew/Library/Homebrew/os/mac/pkgconfig/26"
python3 contrib/macos/scripts/check-opengl.py --app ../dist/PCB-OpenGL.app
python3 contrib/macos/scripts/test-thin-draw.py --app ../dist/PCB-OpenGL.app
python3 contrib/macos/scripts/test-editor.py --app ../dist/PCB-OpenGL.app
python3 contrib/macos/scripts/test-window-size.py --app ../dist/PCB-OpenGL.app
```

`check-opengl.py` checks the real presented OpenGL framebuffer, hardware
acceleration, stencil bits, preview pixels, non-square centering, state
restoration, repeated previews, resizing, zoom and opening Library/DRC. It uses
the public LED example, a test-only GTK module, and a disposable profile. Other
tests cover Thin Draw Poly/Thin Draw, editing, save/reopen and export.
OpenGL intentionally keeps a polygon fill at one quarter of its normal opacity
in thin modes; the GDK renderer shows only the outline. The pixel regression
test checks the corresponding behavior for each renderer. These
checks do not measure frame rate or replace manual testing on large boards.

OpenGL on macOS is a legacy API. This variant remains experimental pending
comparison of interaction, performance and stability with the GDK build.
