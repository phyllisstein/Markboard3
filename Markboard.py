'''
    Grateful thanks to the following people for their work, which constitutes the bricks of this
    little script:
        * Trent Mick, author of python-markdown2 (https://github.com/trentm/python-markdown2),
          which processes the Markdown;
        * Phillip Piper, who wrote the snippet that interacts with the clipboard under Windows; and
        * "Clark," whose guide explained the proper way to use the Foundation and AppKit libraries
          to access OS X's clipboard.
    I can't blame anyone but myself for the gtk scripting, which is as yet untested and likely to be
    less than impeccable; nor for the code's mortar, which largely ditto.
                                                    ---Daniel Shannon, d@daniel.sh, http://daniel.sh

        OS X docs: http://www.libertypages.com/clarktech/?p=3299
     Windows docs: http://code.activestate.com/recipes/474121-getting-html-from-the-windows-clipboard/
       Linux docs: http://www.pygtk.org/docs/pygtk/class-gtkclipboard.html#method-gtkclipboard--store
                   http://developer.gnome.org/gtkmm/stable/classGtk_1_1Clipboard.html
                   http://stackoverflow.com/questions/1992869/how-to-paste-html-to-clipboard-with-gtk
                   http://gtk.php.net/manual/en/gtk.enum.targetflags.php
'''

import codecs
import os
import tempfile
import threading
import subprocess
import sublime
import sublime_plugin
import Markboard3.MarkboardClippers


def err(theError):
    print("[Markboard: " + theError + "]")


class MarkboardCopyFormattedCommand(sublime_plugin.TextCommand):
    def is_enabled(self):
        multimarkdown = self.view.score_selector(0, "text.html.multimarkdown") > 0
        markdown = self.view.score_selector(0, "text.html.markdown") > 0
        return multimarkdown or markdown

    def checkPandoc(self, env):
        cmd = ['pandoc', '--version']
        try:
            output = subprocess.check_output(cmd, env=env)
        except Exception as e:
            err("Exception: " + str(e))

        return output.startswith("pandoc".encode("utf-8"))

    def run(self, edit):
        plat = sublime.platform()
        if plat == "windows":
            sublime.status_message("Windows is unsupported under Sublime 3")
            return
        if plat == "linux":
            sublime.status_message("Linux is unsupported under Sublime 3")
            return

        env = os.environ.copy()
        env['PATH'] = env['PATH'] + ":" + sublime.load_settings("Markboard.sublime-settings").get("pandoc_path", "/usr/local/bin")

        if not self.checkPandoc(env):
            sublime.status_message("Markboard requires Pandoc")
            return

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

        newThread = MarkboardPandocMarkdownProcessor(writer, self.view.window(), env)
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
        else:
            self.view.erase_status("markboard")
            sublime.status_message("Fatal error formatting text.")

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
            return Markboard3.MarkboardClippers.OSXClipObject(self.runningThreadBuffer)
        if plat == "windows":
            self.view.erase_status("markboard")
            sublime.status_message("Windows is unsupported under Sublime 3")
            return None
        if plat == "linux":
            self.view.erase_status("markboard")
            sublime.status_message("Linux is unsupported under Sublime 3")
            return None


class MarkboardPandocMarkdownProcessor(threading.Thread):
    def __init__(self, theFilename, theWindow, env):
        self.myFilename = theFilename
        self.result = None
        self.window = theWindow
        self.env = env
        threading.Thread.__init__(self)

    def run(self):
        f = tempfile.NamedTemporaryFile(mode="w+", suffix=".html", delete=False)
        outFile = f.name
        f.close()
        markdownFrom = "--from=markdown"
        cmd = ['pandoc', self.myFilename, '--output=%s' % outFile, markdownFrom, '--to=html', '--smart', '--normalize']
        try:
            subprocess.call(cmd, env=self.env)
        except Exception as e:
            err("Exception: " + str(e))
            self.result = False
        else:
            f = codecs.open(outFile, "r", "utf-8")
            self.result = f.read()
            f.close()
