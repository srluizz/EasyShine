import sys
import os
import ctypes
import threading
import queue
import traceback
from ctypes import wintypes
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item

# =========================================================
# VERIFICAÇÃO DO SISTEMA
# =========================================================

if sys.platform != "win32":
    raise RuntimeError("EasyShine funciona somente no Windows.")

if ctypes.sizeof(ctypes.c_void_p) != 8:
    raise RuntimeError("Esta versão exige Python de 64 bits.")


# =========================================================
# CONSTANTES WIN32
# =========================================================

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

GWL_EXSTYLE = -20

WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000

WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

LWA_ALPHA = 0x00000002

HWND_TOPMOST = ctypes.c_void_p(-1)

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

WM_QUIT = 0x0012
WM_USER = 0x0400
WM_UPDATE_BRIGHTNESS = WM_USER + 1

BLACK_BRUSH = 4


# =========================================================
# ASSINATURAS WIN32
# =========================================================

user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int

user32.SetWindowLongPtrW.argtypes = [
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_ssize_t
]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t

user32.GetWindowLongPtrW.argtypes = [
    wintypes.HWND,
    ctypes.c_int
]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t

user32.SetLayeredWindowAttributes.argtypes = [
    wintypes.HWND,
    wintypes.COLORREF,
    wintypes.BYTE,
    wintypes.DWORD
]
user32.SetLayeredWindowAttributes.restype = wintypes.BOOL

user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT
]
user32.SetWindowPos.restype = wintypes.BOOL

user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.restype = wintypes.BOOL

user32.RegisterClassW.argtypes = [ctypes.c_void_p]
user32.RegisterClassW.restype = wintypes.WORD

user32.CreateWindowExW.argtypes = [
    wintypes.DWORD,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    wintypes.HMENU,
    wintypes.HINSTANCE,
    wintypes.LPVOID
]
user32.CreateWindowExW.restype = wintypes.HWND

user32.DefWindowProcW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM
]
user32.DefWindowProcW.restype = ctypes.c_ssize_t

user32.GetMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT
]
user32.GetMessageW.restype = ctypes.c_int

user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]

user32.PostThreadMessageW.argtypes = [
    wintypes.DWORD,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM
]
user32.PostThreadMessageW.restype = wintypes.BOOL

user32.PostMessageW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM
]
user32.PostMessageW.restype = wintypes.BOOL

kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE

kernel32.GetCurrentThreadId.restype = wintypes.DWORD

gdi32.GetStockObject.argtypes = [ctypes.c_int]
gdi32.GetStockObject.restype = wintypes.HGDIOBJ


# =========================================================
# ESTRUTURAS WIN32
# =========================================================

WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM
)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HANDLE),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HANDLE),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR)
    ]


# =========================================================
# APLICAÇÃO
# =========================================================

class EasyShineApp:

    def __init__(self):
        self.running = True
        self.current_brightness = 80
        self.overlay_thread_id = None

        self.icon = None
        self.hwnd = None

        self.commands = queue.Queue()
        self.shutdown_lock = threading.Lock()

        self.overlay_ready = threading.Event()
        self.overlay_error = None

        self.overlay_thread = threading.Thread(
            target=self.overlay_worker,
            daemon=True
        )

        self.overlay_thread.start()

        if not self.overlay_ready.wait(timeout=10):
            raise RuntimeError("Tempo esgotado ao iniciar o overlay.")

        if self.overlay_error:
            raise self.overlay_error

        self.setup_tray_icon()
        self.icon.run_detached()

        print("EasyShine iniciado com sucesso.")

    # =====================================================
    # MONITORES
    # =====================================================

    def get_virtual_screen(self):
        x = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        y = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        width = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        height = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        return x, y, width, height

    # =====================================================
    # PROCEDIMENTO DA JANELA (WINDOW PROC)
    # =====================================================

    def window_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_UPDATE_BRIGHTNESS:
            opacity = wparam
            self.apply_opacity_native(opacity)
            return 0

        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    # =====================================================
    # THREAD DO OVERLAY
    # =====================================================

    def overlay_worker(self):
        try:
            self.overlay_thread_id = kernel32.GetCurrentThreadId()

            # Guardar a referência do callback para evitar garbage collection
            self.window_proc_callback = WNDPROC(self.window_proc)

            self.class_name = "EasyShineOverlayWindow"
            instance = kernel32.GetModuleHandleW(None)

            wc = WNDCLASSW()
            wc.style = 0
            wc.lpfnWndProc = self.window_proc_callback
            wc.cbClsExtra = 0
            wc.cbWndExtra = 0
            wc.hInstance = instance
            wc.hIcon = None
            wc.hCursor = None
            wc.hbrBackground = gdi32.GetStockObject(BLACK_BRUSH)
            wc.lpszMenuName = None
            wc.lpszClassName = self.class_name

            atom = user32.RegisterClassW(ctypes.byref(wc))
            if not atom:
                raise ctypes.WinError(ctypes.get_last_error())

            x, y, width, height = self.get_virtual_screen()

            ex_style = (
                WS_EX_LAYERED
                | WS_EX_TRANSPARENT
                | WS_EX_TOOLWINDOW
                | WS_EX_NOACTIVATE
            )

            style = WS_POPUP | WS_VISIBLE

            self.hwnd = user32.CreateWindowExW(
                ex_style,
                self.class_name,
                "EasyShine",
                style,
                x,
                y,
                width,
                height,
                None,
                None,
                instance,
                None
            )

            if not self.hwnd:
                raise ctypes.WinError(ctypes.get_last_error())

            # Define opacidade inicial (80% brilho = ~51 de opacidade preta)
            self.apply_opacity_native(51)

            user32.SetWindowPos(
                self.hwnd,
                HWND_TOPMOST,
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
            )

            self.overlay_ready.set()

            msg = wintypes.MSG()
            while self.running:
                result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result <= 0:
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

        except Exception as error:
            self.overlay_error = error
            self.overlay_ready.set()
            traceback.print_exc()

        finally:
            if self.hwnd:
                user32.DestroyWindow(self.hwnd)
                self.hwnd = None

    # =====================================================
    # OPACIDADE NATIVA (EXECUTADA NA THREAD DA JANELA)
    # =====================================================

    def apply_opacity_native(self, opacity):
        if not self.hwnd:
            return

        opacity = max(0, min(255, int(opacity)))
        user32.SetLayeredWindowAttributes(
            self.hwnd,
            0,
            opacity,
            LWA_ALPHA
        )

    # =====================================================
    # BRILHO
    # =====================================================

    def set_brightness_level(self, brightness):
        if not self.running:
            return

        brightness = max(0, min(100, int(brightness)))
        self.current_brightness = brightness

        # Transforma brilho em opacidade (100% brilho = 0 opacidade, 0% brilho = 255 opacidade)
        opacity = round((100 - brightness) * 255 / 100)

        # Envia mensagem assíncrona para a thread que possui a janela Win32
        if self.hwnd:
            user32.PostMessageW(
                self.hwnd,
                WM_UPDATE_BRIGHTNESS,
                opacity,
                0
            )

        print(f"Brilho selecionado: {brightness}%")

        if self.icon:
            try:
                self.icon.update_menu()
            except Exception:
                pass

    # =====================================================
    # ÍCONE PADRÃO E CARREGAMENTO
    # =====================================================

    def create_default_icon(self):
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((5, 5, 59, 59), fill=(255, 193, 7))
        draw.ellipse((19, 19, 45, 45), fill=(33, 33, 33))
        return img

    def load_icon_image(self):
        # Localiza a pasta temporária criada pelo PyInstaller (--onefile)
        if getattr(sys, "frozen", False):
            base_path = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))

        # Tenta carregar o ícone empacotado ou local
        for icon_name in ["ico.ico", "icon.png"]:
            icon_path = os.path.join(base_path, icon_name)
            if os.path.exists(icon_path):
                try:
                    return Image.open(icon_path).convert("RGBA")
                except Exception:
                    pass

        return self.create_default_icon()

    # =====================================================
    # MENU E BANDEJA
    # =====================================================

    def create_brightness_callback(self, brightness):
        def callback(icon, menu_item):
            if self.running:
                self.commands.put(("brightness", brightness))
        return callback

    def create_brightness_menu(self):
        return [
            item(
                f"Brilho {b}%",
                self.create_brightness_callback(b),
                checked=lambda menu_item, b=b: self.current_brightness == b,
                radio=True
            )
            for b in range(100, -1, -10)
        ]

    def setup_tray_icon(self):
        menu = pystray.Menu(
            *self.create_brightness_menu(),
            pystray.Menu.SEPARATOR,
            item(
                "Sair do EasyShine",
                lambda icon, menu_item: self.commands.put(("quit", None))
            )
        )

        self.icon = pystray.Icon(
            "EasyShine",
            self.load_icon_image(),
            "EasyShine - Controle de Brilho",
            menu
        )

    # =====================================================
    # COMANDOS E ENCERRAMENTO
    # =====================================================

    def process_commands(self):
        while self.running:
            try:
                command, value = self.commands.get(timeout=0.2)

                if command == "brightness":
                    self.set_brightness_level(value)

                elif command == "quit":
                    self.quit_app()
                    break

            except queue.Empty:
                continue

    def quit_app(self):
        with self.shutdown_lock:
            if not self.running:
                return
            self.running = False

        if self.overlay_thread_id:
            user32.PostThreadMessageW(
                self.overlay_thread_id,
                WM_QUIT,
                0,
                0
            )

        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass

    def run(self):
        try:
            self.process_commands()
        finally:
            self.quit_app()
            if self.overlay_thread.is_alive():
                self.overlay_thread.join(timeout=3)


# =========================================================
# INICIALIZAÇÃO
# =========================================================

if __name__ == "__main__":
    app = None
    try:
        app = EasyShineApp()
        app.run()
    except KeyboardInterrupt:
        if app:
            app.quit_app()
    except Exception:
        traceback.print_exc()
        input("\nPressione ENTER para sair...")