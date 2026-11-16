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

WS_POPUP = 0x80000000

WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

LWA_ALPHA = 0x00000002

HWND_TOPMOST = wintypes.HWND(-1)

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_NOZORDER = 0x0004

SW_SHOWNA = 8

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

WM_DESTROY = 0x0002
WM_QUIT = 0x0012
WM_DISPLAYCHANGE = 0x007E
WM_TIMER = 0x0113
WM_USER = 0x0400
WM_UPDATE_BRIGHTNESS = WM_USER + 1
WM_SHUTDOWN_OVERLAY = WM_USER + 2

PM_NOREMOVE = 0x0000
ERROR_CLASS_ALREADY_EXISTS = 1410
BLACK_BRUSH = 4
TIMER_TOPMOST = 1
TOPMOST_INTERVAL_MS = 1000
DEFAULT_BRIGHTNESS = 80
APP_VERSION = "1.0.3"

EVENT_SYSTEM_FOREGROUND = 0x0003
WINEVENT_OUTOFCONTEXT = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0002


# =========================================================
# ASSINATURAS WIN32
# =========================================================

user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int

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

user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL

user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.restype = wintypes.BOOL

user32.RegisterClassW.restype = wintypes.WORD

user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
user32.UnregisterClassW.restype = wintypes.BOOL

user32.SetWinEventHook.restype = wintypes.HANDLE

user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
user32.UnhookWinEvent.restype = wintypes.BOOL

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

user32.PeekMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
    wintypes.UINT
]
user32.PeekMessageW.restype = wintypes.BOOL

user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.TranslateMessage.restype = wintypes.BOOL

user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.restype = ctypes.c_ssize_t

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

user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.PostQuitMessage.restype = None

user32.SetTimer.argtypes = [
    wintypes.HWND,
    ctypes.c_size_t,
    wintypes.UINT,
    ctypes.c_void_p
]
user32.SetTimer.restype = ctypes.c_size_t

user32.KillTimer.argtypes = [wintypes.HWND, ctypes.c_size_t]
user32.KillTimer.restype = wintypes.BOOL

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

WINEVENTPROC = ctypes.WINFUNCTYPE(
    None,
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.HWND,
    wintypes.LONG,
    wintypes.LONG,
    wintypes.DWORD,
    wintypes.DWORD
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


user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.SetWinEventHook.argtypes = [
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HMODULE,
    WINEVENTPROC,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD
]


# =========================================================
# APLICAÇÃO
# =========================================================

class EasyShineApp:

    def __init__(self):
        self.running = True
        self.current_brightness = DEFAULT_BRIGHTNESS
        self.overlay_thread_id = None
        self.class_registered = False
        self.hinstance = None
        self.class_name = "EasyShineOverlayWindow"

        self.icon = None
        self.hwnd = None
        self.overlay_bounds = None
        self.win_event_hook = None
        self.win_event_proc_callback = None

        self.commands = queue.Queue()
        self.shutdown_lock = threading.Lock()
        self.state_lock = threading.Lock()

        self.overlay_ready = threading.Event()
        self.overlay_error = None

        self.overlay_thread = threading.Thread(
            target=self.overlay_worker,
            daemon=True
        )

        try:
            self.overlay_thread.start()

            if not self.overlay_ready.wait(timeout=10):
                raise RuntimeError("Tempo esgotado ao iniciar o overlay.")

            if self.overlay_error:
                raise self.overlay_error

            self.setup_tray_icon()
            self.icon.run_detached()
        except Exception:
            self.quit_app()
            if self.overlay_thread.is_alive():
                self.overlay_thread.join(timeout=3)
            raise

        print("EasyShine iniciado com sucesso.")

    # =====================================================
    # ESTADO THREAD-SAFE
    # =====================================================

    def get_hwnd(self):
        with self.state_lock:
            return self.hwnd

    def set_hwnd(self, hwnd):
        with self.state_lock:
            self.hwnd = hwnd

    def get_brightness(self):
        with self.state_lock:
            return self.current_brightness

    def set_brightness(self, brightness):
        with self.state_lock:
            self.current_brightness = brightness

    @staticmethod
    def brightness_to_opacity(brightness):
        brightness = max(0, min(100, int(brightness)))
        return round((100 - brightness) * 255 / 100)

    def current_opacity(self):
        return self.brightness_to_opacity(self.get_brightness())

    def reapply_current_opacity(self, hwnd=None):
        target = hwnd or self.get_hwnd()
        if not target:
            return False
        return self.apply_opacity_native(target, self.current_opacity())

    # =====================================================
    # MONITORES
    # =====================================================

    def get_virtual_screen(self):
        x = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        y = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        width = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        height = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        return x, y, width, height

    def refresh_overlay_bounds(self, force=False):
        hwnd = self.get_hwnd()
        if not hwnd:
            return False

        x, y, width, height = self.get_virtual_screen()
        if width <= 0 or height <= 0:
            return False

        bounds = (x, y, width, height)
        if not force and bounds == self.overlay_bounds:
            return True

        ok = user32.SetWindowPos(
            hwnd,
            None,
            x,
            y,
            width,
            height,
            SWP_NOZORDER | SWP_NOACTIVATE
        )
        if ok:
            self.overlay_bounds = bounds
            # SetWindowPos em janela layered pode zerar o alpha.
            self.reapply_current_opacity(hwnd)
        return bool(ok)

    def ensure_topmost(self):
        hwnd = self.get_hwnd()
        if not hwnd:
            return False

        ok = user32.SetWindowPos(
            hwnd,
            HWND_TOPMOST,
            0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
        )
        if ok:
            # Reaplica alpha: SetWindowPos pode resetar atributos layered.
            self.reapply_current_opacity(hwnd)
        return bool(ok)

    def on_foreground_changed(
        self,
        h_win_event_hook,
        event,
        hwnd,
        id_object,
        id_child,
        event_thread,
        event_time
    ):
        if event == EVENT_SYSTEM_FOREGROUND and self.running:
            self.ensure_topmost()

    # =====================================================
    # PROCEDIMENTO DA JANELA (WINDOW PROC)
    # =====================================================

    def window_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_UPDATE_BRIGHTNESS:
            self.apply_opacity_native(hwnd, wparam)
            return 0

        if msg == WM_SHUTDOWN_OVERLAY:
            user32.DestroyWindow(hwnd)
            return 0

        if msg == WM_DESTROY:
            user32.KillTimer(hwnd, TIMER_TOPMOST)
            self.set_hwnd(None)
            user32.PostQuitMessage(0)
            return 0

        if msg == WM_DISPLAYCHANGE:
            self.refresh_overlay_bounds(force=True)
            self.ensure_topmost()
            return 0

        if msg == WM_TIMER and wparam == TIMER_TOPMOST:
            # Só reafirma topmost + alpha; não redimensiona a cada tick.
            self.ensure_topmost()
            return 0

        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    # =====================================================
    # THREAD DO OVERLAY
    # =====================================================

    def overlay_worker(self):
        try:
            self.overlay_thread_id = kernel32.GetCurrentThreadId()

            # PeekMessage cria a fila de mensagens da thread antes do ready,
            # evitando falha de PostThreadMessage no shutdown precoce.
            bootstrap_msg = wintypes.MSG()
            user32.PeekMessageW(
                ctypes.byref(bootstrap_msg),
                None,
                0,
                0,
                PM_NOREMOVE
            )

            # Guardar a referência do callback para evitar garbage collection
            self.window_proc_callback = WNDPROC(self.window_proc)

            self.hinstance = kernel32.GetModuleHandleW(None)

            wc = WNDCLASSW()
            wc.style = 0
            wc.lpfnWndProc = self.window_proc_callback
            wc.cbClsExtra = 0
            wc.cbWndExtra = 0
            wc.hInstance = self.hinstance
            wc.hIcon = None
            wc.hCursor = None
            wc.hbrBackground = gdi32.GetStockObject(BLACK_BRUSH)
            wc.lpszMenuName = None
            wc.lpszClassName = self.class_name

            atom = user32.RegisterClassW(ctypes.byref(wc))
            if not atom:
                error_code = ctypes.get_last_error()
                if error_code != ERROR_CLASS_ALREADY_EXISTS:
                    raise ctypes.WinError(error_code)
            else:
                self.class_registered = True

            x, y, width, height = self.get_virtual_screen()
            if width <= 0 or height <= 0:
                raise RuntimeError("Não foi possível obter o tamanho da tela virtual.")

            ex_style = (
                WS_EX_LAYERED
                | WS_EX_TRANSPARENT
                | WS_EX_TOOLWINDOW
                | WS_EX_NOACTIVATE
            )

            # Sem WS_VISIBLE: define alpha antes de exibir para evitar flash preto.
            style = WS_POPUP

            hwnd = user32.CreateWindowExW(
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
                self.hinstance,
                None
            )

            if not hwnd:
                raise ctypes.WinError(ctypes.get_last_error())

            self.set_hwnd(hwnd)
            self.overlay_bounds = (x, y, width, height)

            initial_opacity = self.current_opacity()
            if not self.apply_opacity_native(hwnd, initial_opacity):
                raise ctypes.WinError(ctypes.get_last_error())

            if not user32.SetWindowPos(
                hwnd,
                HWND_TOPMOST,
                x,
                y,
                width,
                height,
                SWP_NOACTIVATE | SWP_SHOWWINDOW
            ):
                # Fallback: pelo menos tenta exibir a janela
                user32.ShowWindow(hwnd, SW_SHOWNA)
                if not self.ensure_topmost():
                    raise ctypes.WinError(ctypes.get_last_error())
            else:
                # SetWindowPos pode resetar o alpha da janela layered.
                if not self.reapply_current_opacity(hwnd):
                    raise ctypes.WinError(ctypes.get_last_error())

            if not user32.SetTimer(hwnd, TIMER_TOPMOST, TOPMOST_INTERVAL_MS, None):
                raise ctypes.WinError(ctypes.get_last_error())

            # Reaplica topmost quando outra janela ganha foco (Explorer, etc.).
            self.win_event_proc_callback = WINEVENTPROC(self.on_foreground_changed)
            self.win_event_hook = user32.SetWinEventHook(
                EVENT_SYSTEM_FOREGROUND,
                EVENT_SYSTEM_FOREGROUND,
                None,
                self.win_event_proc_callback,
                0,
                0,
                WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS
            )

            self.overlay_ready.set()

            msg = wintypes.MSG()
            while True:
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
            if self.win_event_hook:
                user32.UnhookWinEvent(self.win_event_hook)
                self.win_event_hook = None

            hwnd = self.get_hwnd()
            if hwnd:
                user32.KillTimer(hwnd, TIMER_TOPMOST)
                user32.DestroyWindow(hwnd)
                self.set_hwnd(None)

            if self.class_registered and self.hinstance:
                user32.UnregisterClassW(self.class_name, self.hinstance)
                self.class_registered = False

    # =====================================================
    # OPACIDADE NATIVA (EXECUTADA NA THREAD DA JANELA)
    # =====================================================

    def apply_opacity_native(self, hwnd, opacity):
        if not hwnd:
            return False

        opacity = max(0, min(255, int(opacity)))
        ok = user32.SetLayeredWindowAttributes(
            hwnd,
            0,
            opacity,
            LWA_ALPHA
        )
        return bool(ok)

    # =====================================================
    # BRILHO
    # =====================================================

    def set_brightness_level(self, brightness):
        if not self.running:
            return

        brightness = max(0, min(100, int(brightness)))
        self.set_brightness(brightness)
        opacity = self.brightness_to_opacity(brightness)

        hwnd = self.get_hwnd()
        if hwnd:
            if not user32.PostMessageW(
                hwnd,
                WM_UPDATE_BRIGHTNESS,
                opacity,
                0
            ):
                print("Aviso: falha ao enviar atualização de brilho.")

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
                checked=lambda menu_item, b=b: self.get_brightness() == b,
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
            f"EasyShine {APP_VERSION} - Controle de Brilho",
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

        hwnd = self.get_hwnd()
        posted = False

        # Caminho preferencial: mensagem para a janela (fila já existe após CreateWindow).
        if hwnd:
            posted = bool(user32.PostMessageW(hwnd, WM_SHUTDOWN_OVERLAY, 0, 0))

        # Fallback: WM_QUIT na thread (fila criada via PeekMessage no startup).
        if not posted and self.overlay_thread_id:
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
        if app:
            app.quit_app()
            if app.overlay_thread.is_alive():
                app.overlay_thread.join(timeout=3)
        traceback.print_exc()
        input("\nPressione ENTER para sair...")
