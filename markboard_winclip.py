try:
    import ctypes

    strcpy = ctypes.cdll.msvcrt.strcpy
    OpenClipboard = ctypes.windll.user32.OpenClipboard
    EmptyClipboard = ctypes.windll.user32.EmptyClipboard
    SetClipboardData = ctypes.windll.user32.SetClipboardData
    CloseClipboard = ctypes.windll.user32.CloseClipboard
    GlobalAlloc = ctypes.windll.kernel32.GlobalAlloc
    GlobalLock = ctypes.windll.kernel32.GlobalLock
    GlobalUnlock = ctypes.windll.kernel32.GlobalUnlock
    GMEM_DDESHARE = 0x2000
except (ImportError, OSError) as e:
    pass


class MarkboardWinClipper():
    def __init__(self, html):
        self.html = html.replace("\n", "\r\n")

    def copy_html(self):
        header = '''
Format:HTML Format
Version:0.9
StartHTML:<<<<<<<<<<<<<<1
EndHTML:<<<<<<<<<<<<<<2
StartFragment:<<<<<<<<<<<<<<<3
EndFragment:<<<<<<<<<<<<<<4
StartSelection:<<<<<<<<<<<<<<3
EndSelection:<<<<<<<<<<<<<<<3
'''.replace("\n", "\r\n")
        pre = '''
<!DOCTYPE>
<HTML>
<HEAD>
<TITLE>Markboard Clipboard</TITLE>
</HEAD>
<BODY>
<!--StartFragment-->
'''.replace("\n", "\r\n")
        post = '''
<!--EndFragment-->
</BODY>
</HTML>
'''.replace("\n", "\r\n")
        final = header
        start_html = len(final)
        final += pre
        fragment_start = len(final)
        final += self.html
        fragment_end = len(final)
        final += post
        end_html = len(final)

        final.replace("<<<<<<<<<<<<<<1", "{n:15d}".format(n=start_html))
        final.replace("<<<<<<<<<<<<<<2", "{n:15d}".format(n=end_html))
        final.replace("<<<<<<<<<<<<<<3", "{n:15d}".format(n=fragment_start))
        final.replace("<<<<<<<<<<<<<<4", "{n:15d}".format(n=fragment_end))

        opened = OpenClipboard(None)
        if not opened:
            raise WindowsError("Failed to open clipboard.")
        emptied = EmptyClipboard()
        if not emptied:
            CloseClipboard()
            raise WindowsError("Failed to empty clipboard.")

        buff = GlobalAlloc(len(final.encode("utf-8")) + 1)
        if buff == None:
            CloseClipboard()
            raise WindowsError("Failed to allocate clipboard buffer.")
        buff = GlobalLock(buff)
        strcpy(ctypes.c_char_p(buff), final.encode("utf-8"))
        GlobalUnlock(buff)

        data_written = SetClipboardData(13, buff)
        if data_written == None:
            CloseClipboard()
            raise WindowsError("Copy operation failed.")

        CloseClipboard()

        return data_written
