#coding=utf-8

import os
import codecs
import tempfile
import threading
import subprocess
import sublime
import sublime_plugin
import sys
import shutil

PYOBJC_PATH = None


def err(theError):
    print("[Markboard: " + theError + "]")


class MarkboardCopyFormattedCommand(sublime_plugin.ApplicationCommand):
    def is_enabled(self):
        scope = sublime.active_window().active_view().scope_name(0)
        multimarkdown = sublime.score_selector(scope, "text.html.multimarkdown") > 0
        markdown = sublime.score_selector(scope, "text.html.markdown") > 0
        return multimarkdown or markdown

    def is_visible(self):
        return self.is_enabled()

    def checkPandoc(self, env):
        cmd = ['pandoc', '--version']
        try:
            output = subprocess.check_output(cmd, env=env)
        except Exception as e:
            err("Exception: " + str(e))

        return output.startswith("pandoc".encode("utf-8"))

    def run(self):
        plat = sublime.platform()

        self.env = os.environ.copy()
        if plat == "osx" or plat == "linux":
            self.env['PATH'] = self.env['PATH'] + ":" + sublime.load_settings("Markboard.sublime-settings").get("pandoc_path", "/usr/local/bin")
        else:
            self.env['PATH'] = self.env['PATH'] + ";" + sublime.load_settings("Markboard.sublime-settings").get("pandoc_path", "C:\\Program Files\\")

        if not self.checkPandoc(self.env):
            sublime.status_message("Markboard requires Pandoc")
            return

        self.view = sublime.active_window().active_view()

        selections = self.view.sel()
        threads = []

        f = tempfile.NamedTemporaryFile(mode="w+", suffix=".mdown", delete=False)
        writer = f.name
        f.close()
        self.runningThreadBuffer = ""

        singleCursors = passedSelections = 0
        for theSelection in selections:
            theSubstring = self.view.substr(theSelection)
            if len(theSubstring) == 0:
                singleCursors += 1
            else:
                normalString = self.normalize_line_endings(theSubstring)
                f = codecs.open(writer, "a", "utf-8")
                f.write(normalString + "\n\n")
                passedSelections += 1
                f.close()

        if singleCursors > 0 and passedSelections < 1:
            theBuffer = self.view.substr(sublime.Region(0, self.view.size()))
            normalString = self.normalize_line_endings(theBuffer)
            f = codecs.open(writer, "a", "utf-8")
            f.write(normalString + "\n\n")
            f.close()

        newThread = MarkboardPandocMarkdownProcessor(writer, self.env)
        threads.append(newThread)
        newThread.start()

        self.manageThreads(threads)

    def manageThreads(self, theThreads, offset=0, i=0, direction=1):
        next_threads = []
        for aThread in theThreads:
            if aThread.is_alive():
                next_threads.append(aThread)
                continue
            self.runningThreadBuffer += "\n\n"
            self.runningThreadBuffer += aThread.result
        theThreads = next_threads

        if len(theThreads):
            before = i % 8
            after = 7 - before
            if not after:
                direction = -1
            if not before:
                direction = 1
            i += direction
            self.view.set_status("markboard", "Markdown markup... [%s=%s]" %
                                 (" " * before, " " * after))

            sublime.set_timeout(lambda: self.manageThreads(theThreads, offset, i, direction), 100)
            return

        clipObject = self.clipboardCopy()
        if clipObject:
            self.view.erase_status("markboard")
            sublime.status_message("Formatted text copied.")

    def normalize_line_endings(self, string):
        string = string.replace('\r\n', '\n').replace('\r', '\n')
        line_endings = self.view.settings().get('default_line_ending')
        if line_endings == 'windows':
            string = string.replace('\n', '\r\n')
        elif line_endings == 'mac':
            string = string.replace('\n', '\r')
        return string

    def clipboardCopy(self):
        plat = sublime.platform()
        if plat == "osx":
            if "sublime-package" in __file__:
                import zipfile
                package_path, _ = os.path.split(__file__)
                cache_path = tempfile.mkdtemp()
                global PYOBJC_PATH
                PYOBJC_PATH = cache_path
                with zipfile.ZipFile(package_path) as z:
                    for m in z.namelist():
                        m_dir, m_base = os.path.split(m)
                        if "PyObjC" in m and m_base:
                            src = z.open(m)
                            dirtree = os.path.join(cache_path, m_dir)
                            if not os.path.exists(dirtree):
                                os.makedirs(dirtree)
                            trg = open(os.path.join(cache_path, m), "wb")
                            with src, trg:
                                shutil.copyfileobj(src, trg)
                sys.path.insert(0, os.path.join(cache_path, "PyObjC"))
            else:
                script_dir = os.path.dirname(__file__)
                module_path = os.path.join(script_dir, "PyObjC")
                sys.path.insert(0, module_path)
            try:
                import Foundation
                import AppKit
            except ImportError as e:
                print("[Markboard3: Failed to copy PyObjC module with exception:]")
                print("[{e}]".format(e=e))

            pasteboard = AppKit.NSPasteboard.generalPasteboard()
            typeArray = Foundation.NSArray.arrayWithObject_(AppKit.NSHTMLPboardType)
            pasteboard.declareTypes_owner_(typeArray, None)
            return pasteboard.setString_forType_(self.runningThreadBuffer, AppKit.NSHTMLPboardType)
        if plat == "windows":
            import Markboard3.markboard_winclip as winc

            wc = winc.MarkboardWinClipper(self.runningThreadBuffer)
            return wc.copy_html()
        if plat == "linux":
            final_file = tempfile.NamedTemporaryFile(suffix=".html", mode="w+", delete=False)
            final_file.write(self.runningThreadBuffer)
            final_file.close()
            cmd = ['xclip', '-i', final_file.name, '-selection', 'clipboard',
                    '-t', 'text/html']
            try:
                subprocess.check_call(cmd, env=self.env)
            except subprocess.CalledProcessError as e:
                err("Call to xclip failed with exception: {e}".format(e=e))
                return False
            return True


class MarkboardPandocMarkdownProcessor(threading.Thread):
    def __init__(self, theFilename, env):
        self.myFilename = theFilename
        self.result = None
        self.env = env
        threading.Thread.__init__(self)

    def run(self):
        f = tempfile.NamedTemporaryFile(mode="w+", suffix=".html", delete=False)
        outFile = f.name
        f.close()
        g = tempfile.NamedTemporaryFile(mode="w+", suffix=".html", delete=False)
        empty_template = sublime.load_resource("Packages/Markboard3/template-empty.html")
        g.write(empty_template)
        g.close()
        md = 'markdown+hard_line_breaks+intraword_underscores+strikeout+superscript+\
              subscript+inline_code_attributes+all_symbols_escapable+yaml_metadata_block+\
              pipe_tables+grid_tables+multiline_tables+table_captions+simple_tables+\
              example_lists+definition_lists+startnum+fancy_lists+fenced_code_attributes+\
              fenced_code_blocks+backtick_code_blocks+blank_before_blockquote+\
              implicit_header_references+auto_identifiers+header_attribuets+\
              blank_before_header+escaped_line_breaks'
        cmd = ['pandoc', self.myFilename, '--output=%s' % outFile, '--from=%s' % md,
               '--to=html5', '--smart', '--normalize', '--email-obfuscation=none',
               '--template=%s' % g.name]
        try:
            subprocess.call(cmd, env=self.env)
        except Exception as e:
            err("Exception: " + str(e))
            self.result = False
        else:
            f = codecs.open(outFile, "r", "utf-8")
            self.result = f.read()
            f.close()

def plugin_unloaded():
    if PYOBJC_PATH:
        shutil.rmtree(PYOBJC_PATH)
