import os
import io
import json
import subprocess
import tempfile
import PyPDF2
import pdfplumber
import pytesseract
import simplejson
from tkinter import Tk
from tkinter import *
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw
from wand.exceptions import WandException

from gui import FIELDS
from gui.viewer import PDFViewer
from gui.custom_widgets import HoverButton, MenuBox, Logger, StoppableThread

class Extractor(Frame):

    def __init__(self, master=None, **kw):
        Frame.__init__(self, master, **kw)
        self.background = '#303030'
        self.border_color = '#404040'
        self.checkbox_color = '#333333'
        self.highlight_color = '#558de8'
        self.pdf = None
        self.paths = list()
        self.pathidx = -1
        self.checkboxes = {}
        self.thread = None
        self.running = False
        self.save_dir = '.'
        self.info_dict = {}
        self._init_ui()

    def _init_ui(self):
        ws = self.master.winfo_screenwidth()
        hs = self.master.winfo_screenheight()
        h = hs - 100
        w = (int(h / 1.414) + 100) * 2
        x = (ws / 2) - (w / 2)
        y = (hs / 2) - (h / 2)
        self.master.geometry('%dx%d+%d+%d' % (w, h, x, y))
        self.master.maxsize(w, h)
        self.master.minsize(w, h)
        self.master.title("InvoiceNet")

        self.pack(fill=BOTH, expand=True)

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=0)

        tool_frame = Frame(self, bg=self.background, bd=0, relief=SUNKEN)
        self.viewer = PDFViewer(self)
        interface = Frame(self, bg=self.background, bd=0, relief=SUNKEN,
                          highlightbackground=self.border_color, highlightthickness=1)

        tool_frame.grid(row=0, column=0, sticky='news')
        self.viewer.grid(row=0, column=1, sticky='news')
        interface.grid(row=0, column=2, sticky='news')

        # Tool Frame
        tool_frame.columnconfigure(0, weight=1)
        tool_frame.rowconfigure(0, weight=0)
        tool_frame.rowconfigure(1, weight=1)
        tool_frame.rowconfigure(2, weight=0)
        tool_frame.rowconfigure(3, weight=2)

        options = MenuBox(tool_frame, image_path=r'widgets/options.png', bg=self.background)
        options.grid(row=0, column=0)

        options.add_item('Open Files...', self._open_file)
        options.add_item('Open Directory...', self._open_dir, seperator=True)
        options.add_item('Set Save Directory...', self._set_save_path, seperator=True)
        options.add_item('Next File', self._next_file)
        options.add_item('Previous File', self._prev_file, seperator=True)
        options.add_item('Clear Page', self.viewer.clear)
        options.add_item('Search Text', self.viewer.search_text)
        options.add_item('Extract Text', self.viewer.extract_text)
        options.add_item('Run OCR', self._run_ocr, seperator=True)
        options.add_item('Clear Invoice Queue', self._clear_queue, seperator=True)
        options.add_item('Help...', self._help, seperator=True)
        options.add_item('Exit', self.master.quit)

        tools = Frame(tool_frame, bg=self.background, bd=0, relief=SUNKEN)
        tools.grid(row=2, column=0)

        HoverButton(tools, image_path=r'widgets/open_file.png', command=self._open_file,
                    width=50, height=50, bg=self.background, bd=0, tool_tip="Open Files",
                    highlightthickness=0, activebackground=self.highlight_color).pack(pady=2)
        HoverButton(tools, image_path=r'widgets/open_dir.png', command=self._open_dir,
                    width=50, height=50, bg=self.background, bd=0, tool_tip="Open Directory",
                    highlightthickness=0, activebackground=self.highlight_color).pack(pady=2)
        HoverButton(tools, image_path=r'widgets/save_as.png', command=self._set_save_path,
                    width=50, height=50, bg=self.background, bd=0, tool_tip="Set Save Directory",
                    highlightthickness=0, activebackground=self.highlight_color).pack(pady=2)
        HoverButton(tools, image_path=r'widgets/clear_page.png', command=self.viewer.clear,
                    width=50, height=50, bg=self.background, bd=0, tool_tip="Clear Page",
                    highlightthickness=0, activebackground=self.highlight_color).pack(pady=2)
        HoverButton(tools, image_path=r'widgets/search.png', command=self.viewer.search_text,
                    width=50, height=50, bg=self.background, bd=0, tool_tip="Search Text",
                    highlightthickness=0, activebackground=self.highlight_color).pack(pady=2)
        HoverButton(tools, image_path=r'widgets/extract.png', command=self.viewer.extract_text,
                    width=50, height=50, bg=self.background, bd=0, tool_tip="Extract Text",
                    highlightthickness=0, activebackground=self.highlight_color).pack(pady=2)
        HoverButton(tools, image_path=r'widgets/ocr.png', command=self._run_ocr,
                    width=50, height=50, bg=self.background, bd=0, tool_tip="Run OCR",
                    highlightthickness=0, activebackground=self.highlight_color).pack(pady=2)
        HoverButton(tools, image_path=r'widgets/clear_all.png', command=self._clear_queue,
                    width=50, height=50, bg=self.background, bd=0, tool_tip="Clear Invoice Queue",
                    highlightthickness=0, activebackground=self.highlight_color).pack(pady=2)

        file_frame = Frame(tools, width=50, height=50, bg=self.background, bd=0, relief=SUNKEN)
        file_frame.pack(pady=2)

        file_frame.columnconfigure(0, weight=1)
        file_frame.columnconfigure(1, weight=1)

        HoverButton(file_frame, image_path=r'widgets/prev_file.png', command=self._prev_file,
                    width=25, height=50, bg=self.background, bd=0, tool_tip="Previous File",
                    highlightthickness=0, activebackground=self.highlight_color).grid(row=0, column=0)
        HoverButton(file_frame, image_path=r'widgets/next_file.png', command=self._next_file,
                    width=25, height=50, bg=self.background, bd=0, tool_tip="Next File",
                    highlightthickness=0, activebackground=self.highlight_color).grid(row=0, column=1)

        self.doc_label = Label(file_frame, bg=self.background, bd=0, fg='white', font=("Arial", 8), text="0 of 0")
        self.doc_label.grid(row=1, column=0, columnspan=2, pady=4, sticky='news')

        HoverButton(tool_frame, image_path=r'widgets/help.png', command=self._help,
                    width=50, height=50, bg=self.background, bd=0, tool_tip="Help",
                    highlightthickness=0, activebackground=self.highlight_color).grid(row=3, column=0, sticky='s')

        # Interface Frame
        interface.columnconfigure(0, weight=1)
        interface.rowconfigure(0, weight=0)
        interface.rowconfigure(1, weight=1)
        interface.rowconfigure(2, weight=1)

        logo_frame = Frame(interface, bg=self.background, bd=0, relief=SUNKEN,
                           highlightbackground=self.border_color, highlightthickness=1)
        param_frame = Frame(interface, bg=self.background, bd=0, relief=SUNKEN,
                            highlightbackground=self.border_color, highlightthickness=1)
        main_frame = Frame(interface, bg=self.background, bd=0, relief=SUNKEN,
                           highlightbackground=self.border_color, highlightthickness=1)

        logo_frame.grid(row=0, column=0, sticky='news')
        param_frame.grid(row=1, column=0, sticky='news')
        main_frame.grid(row=2, column=0, sticky='news')

        # Logo Frame
        logo_frame.columnconfigure(0, weight=1)
        logo_frame.columnconfigure(1, weight=0)
        logo_frame.columnconfigure(2, weight=0)
        logo_frame.columnconfigure(3, weight=1)
        logo_frame.rowconfigure(0, weight=1)

        self.logo_img = ImageTk.PhotoImage(Image.open(r'widgets/logo.png'))
        Label(logo_frame, bg=self.background, image=self.logo_img).grid(row=0, column=1, sticky='news', pady=10)
        Label(logo_frame, text="InvoiceNet", bg=self.background,
              fg="white", font=("Arial", 24, "bold")).grid(row=0, column=2, sticky='news', padx=20, pady=10)

        # Param Frame
        param_frame.columnconfigure(0, weight=1)
        param_frame.columnconfigure(1, weight=2)
        param_frame.columnconfigure(2, weight=1)
        param_frame.rowconfigure(0, weight=1)
        param_frame.rowconfigure(1, weight=2)
        param_frame.rowconfigure(2, weight=1)

        self.start_button = HoverButton(param_frame, image_path=r'widgets/begin.png', command=self._save_labels,
                                        text='Set Labels', compound='center', font=("Arial", 10, "bold"), bd=0,
                                        bg=self.background, highlightthickness=0, activebackground=self.background)
        self.start_button.grid(row=2, column=1, pady=20, sticky='news')

        field_param = Frame(param_frame, bg=self.background, bd=0, relief=SUNKEN,
                            highlightbackground=self.border_color, highlightthickness=0)

        field_param.grid(row=1, column=1, sticky='news')

        # Field Checkboxes
        field_frame = Frame(field_param, bg=self.checkbox_color, bd=0, relief=SUNKEN,
                            highlightbackground=self.border_color, highlightthickness=1)
        field_frame.pack(expand=True, fill=BOTH)

        Label(field_frame, text="Field:", width=30, bg=self.checkbox_color,
              anchor='w', fg="white", font=("Arial", 12, "bold")).pack(side=TOP, fill=X, padx=5, pady=5)

        checkbox_frame = Frame(field_frame, bg=self.checkbox_color, bd=0, relief=SUNKEN,
                               highlightbackground=self.border_color, highlightthickness=1)
        checkbox_frame.pack(expand=True, fill=BOTH, side=BOTTOM)

        checkbox_frame.columnconfigure(0, weight=1)
        checkbox_frame.columnconfigure(1, weight=1)
        checkbox_frame.columnconfigure(2, weight=1)
        checkbox_frame.columnconfigure(3, weight=1)
        for i in range(len(FIELDS) // 2):
            checkbox_frame.rowconfigure(i, weight=1)
        for idx, key in enumerate(FIELDS):
            self.checkboxes[key] = BooleanVar(checkbox_frame, value=False)

            Checkbutton(checkbox_frame, fg="black", bg=self.checkbox_color,
                        activebackground=self.checkbox_color, variable=self.checkboxes[key],
                        highlightthickness=0).grid(row=idx // 2, 
                                                   column=2 if idx % 2 else 0, 
                                                   sticky='news', padx=(10, 0))
            Label(checkbox_frame, text=key, bg=self.checkbox_color,
                  fg="white", font=("Arial", 12, "bold")).grid(row=idx // 2, column=3 if idx % 2 else 1, sticky='nws')

        # Main Frame
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.columnconfigure(2, weight=1)
        main_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
        main_frame.rowconfigure(3, weight=1)

        self.logger = Logger(main_frame, disable=False, height=18, bg=self.background, bd=0, relief=SUNKEN)
        self.logger.grid(row=1, column=1, sticky='news')

        button_frame = Frame(main_frame, bg=self.background, bd=0, relief=SUNKEN,
                             highlightbackground=self.border_color, highlightthickness=0)
        button_frame.grid(row=2, column=1, sticky='news')

        button_frame.rowconfigure(0, weight=1)
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=0)
        button_frame.columnconfigure(2, weight=0)
        button_frame.columnconfigure(3, weight=1)

        HoverButton(button_frame, image_path=r'widgets/labels.png', command=self._save_info, text='Save Labels',
                    compound='center', font=("Arial", 10, "bold"), bd=0, bg=self.background,
                    highlightthickness=0, activebackground=self.background).grid(row=0, column=1, padx=10)

        HoverButton(button_frame, image_path=r'widgets/labels.png', command=self._load_labels, text='Load Labels',
                    compound='center', font=("Arial", 10, "bold"), bd=0, bg=self.background,
                    highlightthickness=0, activebackground=self.background).grid(row=0, column=2, padx=10)

    def _set_label(self):
        pass
    
    def _extract(self):
        pass

    def _save_labels(self):
        if not self.paths:
            messagebox.showerror("Error", "No PDF has been loaded!")
            return

        selected = False
        for key in FIELDS:
            if self.checkboxes[key].get():
                selected = True
                rect = self.viewer.bbox
                self.info_dict['fields'][key] = {'text': rect['text'], 
                                                 'location': [int(rect['x0']), int(rect['top']), 
                                                              int(rect['x1']), int(rect['bottom'])]}
                self.logger.log("Field Name:'{}'\nText:'{}'\nLocation:[({}, {}), ({}, {})]\n".format(
                    key, rect['text'], int(rect['x0']), int(rect['top']), int(rect['x1']), int(rect['bottom'])))
                self.checkboxes[key].set(False)
                break

        if not selected:
            messagebox.showerror("Error", "No fields were selected!")
            return

    def _load_labels(self):
        if not self.paths:
            messagebox.showerror("Error", "No PDF has been loaded!")
            return
        label_file = filedialog.askopenfile(filetypes=[('JSON files', '*.json'), ('all files', '.*')],
                                            initialdir=self.save_dir, title="Select label file")
        if label_file is None:
            return
        try:
            labels = simplejson.load(label_file)
            infos = self.viewer._load_labels_and_get_info(labels)
            if infos is None:
                return
            for info in infos:
                self.logger.log("Field Name:'{}'\nText:'{}'\nLocation:[({}, {}), ({}, {})]\n...\n".format(
                        info['label'], info['text'], int(info['bbox']['x0']), int(info['bbox']['top']), int(info['bbox']['x1']), int(info['bbox']['bottom'])))
        except simplejson.errors.JSONDecodeError:
            messagebox.showerror("Error", "JSON file is invalid!")
            return
        pass
    
    def _save_info(self):
        file_name = os.path.splitext(os.path.basename(self.info_dict['path']))[0]
        with open(self.save_dir + "/" + file_name + ".json","w") as f:
            json.dump(self.info_dict, f)
        self.logger.log("Information has been saved in '{}'".format(self.save_dir + "/" + file_name + ".json"))

    def _set_save_path(self):
        path = filedialog.askdirectory(title='Set Save Directory', initialdir=self.save_dir)
        if path == '' or not path:
            return
        if not os.path.exists(path):
            messagebox.showerror("Error", "Invalid directory!")
            return
        self.save_dir = path
        self.logger.log("Information will now be saved in '{}'".format(self.save_dir))

    def _next_file(self):
        if self.pathidx == len(self.paths) - 1 or len(self.paths) == 0:
            return
        self.pathidx += 1
        self._load_file()

    def _prev_file(self):
        if self.pathidx == 0 or len(self.paths) == 0:
            return
        self.pathidx -= 1
        self._load_file()

    def _run_ocr(self):
        if self.pdf is None:
            return

        pdf_pages = list()
        for page in self.pdf.pages:
            image = page.to_image(resolution=100)
            
            # myocr
            # text_strings, text_recs_alls = predict([image.original], language='jpn')
            # boxes = [[(recs[0], recs[1]), (recs[4], recs[5])] for recs in text_recs_alls[0]][:-1]
            # imgdraw = ImageDraw.Draw(image.original)
            # for box in boxes:
            #     imgdraw.rectangle(box,width=2,outline='red')
            # 画框
            # boxes = [box.split(' ') for box in pytesseract.image_to_boxes(image.original).split('\n')][:-1]
            # imgcopy = image.original.copy()
            # imgdraw = ImageDraw.Draw(imgcopy)
            # for box in boxes:
            #     x1,y1,x2,y2 = int(box[1]),int(box[2]),int(box[3]),int(box[4])
            #     imgdraw.rectangle([(x1,y1),(x2,y2)],width=2,outline='red')
            
            pdf = pytesseract.image_to_pdf_or_hocr(image.original, extension='pdf')
            pdf_pages.append(pdf)

        pdf_writer = PyPDF2.PdfFileWriter()
        for page in pdf_pages:
            pdf = PyPDF2.PdfFileReader(io.BytesIO(page))
            pdf_writer.addPage(pdf.getPage(0))

        pdf = io.BytesIO()
        pdf_writer.write(pdf)

        self.pdf = pdfplumber.load(pdf)
        self.viewer.display_pdf(self.pdf)

    def _load_file(self):
        self.viewer.clear()
        path = self.paths[self.pathidx]
        filename = os.path.basename(path)
        try:
            if filename.split('.')[-1].lower() in ['jpg', 'png']:
                image = Image.open(path)
                pdf = io.BytesIO(pytesseract.image_to_pdf_or_hocr(image, extension='pdf'))
                self.pdf = pdfplumber.load(pdf)
            else:
                self.pdf = pdfplumber.open(path)
            self.viewer.display_pdf(self.pdf)
            self.doc_label.configure(text="{} of {}".format(self.pathidx + 1, len(self.paths)))
            self.logger.clear()
            self.logger.log("Showing invoice '{}'".format(path))
            self.info_dict = {"path": path, "fields": {}}
        except WandException:
            result = messagebox.askokcancel("Error",
                                            "ImageMagick Policy Error! Should InvoiceNet try to fix the error?")
            if result:
                result = self._fix_policy_error()
            if result:
                messagebox.showinfo("Policy Fixed!", "ImageMagick Policy Error fixed! Restart InvoiceNet.")
            else:
                messagebox.showerror("ImageMagick Policy Error",
                                     "Coud not fix ImageMagick policy. Rejecting the current pdf file!")
        except (IndexError, IOError, TypeError):
            pass

    def _open_file(self):
        paths = filedialog.askopenfilenames(filetypes=[('PDF files', '*.pdf'),
                                                       ('JPG files', '*.jpg'),
                                                       ('PNG files', '*.png'),
                                                       ('all files', '.*')],
                                            initialdir='.',
                                            title="Select files", multiple=True)
        if not paths or paths == '':
            return
        paths = [path for path in paths if os.path.basename(path).split('.')[-1].lower() in ['pdf', 'jpg', 'png']]
        self.paths = self.paths[:self.pathidx + 1] + paths + self.paths[self.pathidx + 1:]
        self.pathidx += 1
        self._load_file()

    def _open_dir(self):
        dir_name = filedialog.askdirectory(initialdir='.', title="Select Directory Containing Invoices")
        if not dir_name or dir_name == '':
            return
        paths = os.listdir(dir_name)
        paths = [os.path.join(dir_name, path) for path in paths
                 if os.path.basename(path).split('.')[-1].lower() in ['pdf', 'jpg', 'png']]
        self.paths = self.paths[:self.pathidx + 1] + paths + self.paths[self.pathidx + 1:]
        if not self.paths:
            return
        self.pathidx += 1
        self._load_file()

    def _clear_queue(self):
        self.viewer.reset()
        self.logger.clear()
        self.pdf = None
        self.paths = list()
        self.info_dict = {}
        self.pathidx = -1
        self.doc_label.configure(text="{} of {}".format(self.pathidx + 1, len(self.paths)))
        self.thread = None
        self.running = False

    def _help(self):
        ws = self.master.winfo_screenwidth()
        hs = self.master.winfo_screenheight()
        w, h = 600, 600
        x = (ws / 2) - (w / 2)
        y = (hs / 2) - (h / 2)
        help_frame = Toplevel(self)
        help_frame.title("Help")
        help_frame.configure(width=w, height=h, bg=self.background, relief=SUNKEN)
        help_frame.geometry('%dx%d+%d+%d' % (w, h, x, y))
        help_frame.minsize(height=h, width=w)
        help_frame.maxsize(height=h, width=w)
        help_frame.rowconfigure(0, weight=1)
        help_frame.columnconfigure(0, weight=1)
        HelpBox(help_frame, width=w, height=h, bg=self.background, relief=SUNKEN).grid(row=0, column=0)

    @staticmethod
    def _fix_policy_error():
        policy_path = "/etc/ImageMagick-6/policy.xml"

        if not os.path.isfile(policy_path):
            policy_path = "/etc/ImageMagick/policy.xml"

        if not os.path.exists(policy_path):
            return False

        try:
            with open(policy_path, 'r') as policy_file:
                data = policy_file.readlines()
                new_data = []

                for line in data:
                    if 'MVG' in line:
                        line = '<!-- ' + line + ' -->'
                    elif 'PDF' in line:
                        line = '  <policy domain="coder" rights="read|write" pattern="PDF" />\n'
                    elif '</policymap>' in line:
                        new_data.append('  <policy domain="coder" rights="read|write" pattern="LABEL" />\n')
                    new_data.append(line)

                temp = tempfile.NamedTemporaryFile(mode='w', suffix='.xml')
                temp.writelines(new_data)
                subprocess.call(["sudo", "mv", temp.name, policy_path])
        except (IndexError, IOError, TypeError):
            return False
        

    
if __name__ == '__main__':
    root = Tk()
    Extractor(root)
    root.mainloop()