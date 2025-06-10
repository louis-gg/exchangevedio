import os
import sys
import subprocess
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from tkinter.font import Font

class VideoConverter:
    def __init__(self, input_dir, output_dir, ffmpeg_path, src_formats, dst_format, preserve_structure=True):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.ffmpeg_path = ffmpeg_path
        self.src_formats = src_formats
        self.dst_format = dst_format
        self.preserve_structure = preserve_structure
        self.cancel_flag = False
        self.log_queue = queue.Queue()
        self.progress_queue = queue.Queue()
        self.total_files = 0
        self.processed_files = 0

    def get_video_files(self):
        """获取所有需要转换的视频文件"""
        video_files = []
        if self.preserve_structure:
            for root, _, files in os.walk(self.input_dir):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in self.src_formats):
                        video_files.append((root, file))
        else:
            for file in os.listdir(self.input_dir):
                if any(file.lower().endswith(ext) for ext in self.src_formats):
                    video_files.append((self.input_dir, file))
        return video_files

    def convert_video(self, input_path, output_path):
        """转换单个视频文件"""
        # 根据目标格式设置编码参数
        if self.dst_format == '.mp4':
            cmd = [
                self.ffmpeg_path,
                '-i', input_path,
                '-c:v', 'libx264',
                '-crf', '23',
                '-preset', 'medium',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-y',
                output_path
            ]
        elif self.dst_format == '.webm':
            cmd = [
                self.ffmpeg_path,
                '-i', input_path,
                '-c:v', 'libvpx-vp9',
                '-crf', '30',
                '-b:v', '0',
                '-c:a', 'libopus',
                '-b:a', '128k',
                '-y',
                output_path
            ]
        elif self.dst_format == '.avi':
            cmd = [
                self.ffmpeg_path,
                '-i', input_path,
                '-c:v', 'mpeg4',
                '-q:v', '3',
                '-c:a', 'mp3',
                '-b:a', '128k',
                '-y',
                output_path
            ]
        elif self.dst_format == '.mov':
            cmd = [
                self.ffmpeg_path,
                '-i', input_path,
                '-c:v', 'h264',
                '-crf', '23',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-y',
                output_path
            ]
        else:
            # 默认使用原始编码
            cmd = [
                self.ffmpeg_path,
                '-i', input_path,
                '-c', 'copy',
                '-y',
                output_path
            ]
        
        try:
            result = subprocess.run(
                cmd, 
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return True, result.stderr
        except subprocess.CalledProcessError as e:
            return False, e.stderr
        except Exception as e:
            return False, str(e)

    def start_conversion(self):
        """开始转换过程"""
        self.log_queue.put("🚀 开始转换视频...")
        self.log_queue.put(f"输入目录: {self.input_dir}")
        self.log_queue.put(f"输出目录: {self.output_dir}")
        self.log_queue.put(f"源格式: {', '.join(self.src_formats)}")
        self.log_queue.put(f"目标格式: {self.dst_format}")
        self.log_queue.put(f"保留目录结构: {'是' if self.preserve_structure else '否'}")
        self.log_queue.put("-" * 60)
        
        video_files = self.get_video_files()
        self.total_files = len(video_files)
        self.processed_files = 0
        
        if self.total_files == 0:
            self.log_queue.put("❌ 没有找到可转换的视频文件")
            self.progress_queue.put((0, 0, "没有可转换的文件"))
            return
        
        for root, file in video_files:
            if self.cancel_flag:
                self.log_queue.put("⚠️ 转换已取消")
                break
                
            input_path = os.path.join(root, file)
            
            # 处理输出路径
            if self.preserve_structure:
                rel_path = os.path.relpath(root, self.input_dir)
                output_subdir = os.path.join(self.output_dir, rel_path)
                os.makedirs(output_subdir, exist_ok=True)
                output_file = os.path.splitext(file)[0] + self.dst_format
                output_path = os.path.join(output_subdir, output_file)
            else:
                output_file = os.path.splitext(file)[0] + self.dst_format
                output_path = os.path.join(self.output_dir, output_file)
            
            # 记录开始转换
            self.log_queue.put(f"转换中: {file} → {output_file}")
            self.progress_queue.put((self.processed_files, self.total_files, f"处理: {file}"))
            
            # 执行转换
            success, log = self.convert_video(input_path, output_path)
            
            if success:
                self.log_queue.put(f"✓ 转换成功: {file}")
            else:
                self.log_queue.put(f"❌ 转换失败: {file}")
                self.log_queue.put(f"错误信息: {log[:200]}...")  # 只显示前200个字符
            
            self.processed_files += 1
            progress = int((self.processed_files / self.total_files) * 100)
            self.progress_queue.put((self.processed_files, self.total_files, 
                                   f"进度: {self.processed_files}/{self.total_files} ({progress}%)"))
        
        if self.cancel_flag:
            self.log_queue.put("⏹️ 转换已取消")
            self.progress_queue.put((self.processed_files, self.total_files, "转换已取消"))
        else:
            self.log_queue.put("=" * 60)
            self.log_queue.put(f"✅ 转换完成! 成功转换 {self.processed_files}/{self.total_files} 个文件")
            self.progress_queue.put((self.processed_files, self.total_files, "转换完成"))

    def cancel(self):
        """取消转换"""
        self.cancel_flag = True
        self.log_queue.put("正在取消转换...")


class VideoConverterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("视频格式批量转换工具")
        self.geometry("800x600")
        self.resizable(True, True)
        
        # 设置应用图标（如果有的话）
        try:
            self.iconbitmap("video_icon.ico")
        except:
            pass
        
        # 创建样式
        self.style = ttk.Style()
        self.style.configure("TButton", padding=6, font=("Segoe UI", 10))
        self.style.configure("TLabel", font=("Segoe UI", 10))
        self.style.configure("TFrame", background="#f0f0f0")
        self.style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"), foreground="#2c3e50")
        
        # 创建主框架
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 标题
        header = ttk.Label(main_frame, text="视频格式批量转换工具", style="Header.TLabel")
        header.pack(pady=(0, 15))
        
        # 输入输出目录框架
        io_frame = ttk.LabelFrame(main_frame, text="目录设置")
        io_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 输入目录
        input_frame = ttk.Frame(io_frame)
        input_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(input_frame, text="输入目录:").pack(side=tk.LEFT, padx=(0, 5))
        self.input_dir = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.input_dir, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(input_frame, text="浏览...", command=self.select_input_dir).pack(side=tk.LEFT)
        
        # 输出目录
        output_frame = ttk.Frame(io_frame)
        output_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(output_frame, text="输出目录:").pack(side=tk.LEFT, padx=(0, 5))
        self.output_dir = tk.StringVar()
        ttk.Entry(output_frame, textvariable=self.output_dir, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(output_frame, text="浏览...", command=self.select_output_dir).pack(side=tk.LEFT)
        
        # FFmpeg设置框架
        ffmpeg_frame = ttk.LabelFrame(main_frame, text="FFmpeg设置")
        ffmpeg_frame.pack(fill=tk.X, pady=(0, 10))
        
        ffmpeg_path_frame = ttk.Frame(ffmpeg_frame)
        ffmpeg_path_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(ffmpeg_path_frame, text="FFmpeg路径:").pack(side=tk.LEFT, padx=(0, 5))
        self.ffmpeg_path = tk.StringVar()
        
        # 尝试查找默认的FFmpeg路径
        default_ffmpeg = self.find_default_ffmpeg()
        if default_ffmpeg:
            self.ffmpeg_path.set(default_ffmpeg)
        else:
            self.ffmpeg_path.set("ffmpeg")  # 默认使用系统路径中的ffmpeg
            
        ttk.Entry(ffmpeg_path_frame, textvariable=self.ffmpeg_path, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(ffmpeg_path_frame, text="浏览...", command=self.select_ffmpeg).pack(side=tk.LEFT)
        ttk.Button(ffmpeg_path_frame, text="测试", command=self.test_ffmpeg).pack(side=tk.LEFT, padx=(5, 0))
        
        # 格式设置框架
        format_frame = ttk.LabelFrame(main_frame, text="格式设置")
        format_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 源格式选择
        src_format_frame = ttk.Frame(format_frame)
        src_format_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(src_format_frame, text="源格式:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.src_formats = {
            '.mpg': tk.BooleanVar(value=True),
            '.avi': tk.BooleanVar(value=True),
            '.mov': tk.BooleanVar(value=False),
            '.mkv': tk.BooleanVar(value=False),
            '.flv': tk.BooleanVar(value=False),
            '.wmv': tk.BooleanVar(value=False),
            '.mp4': tk.BooleanVar(value=False),
            '.m4v': tk.BooleanVar(value=False)
        }
        
        for i, (ext, var) in enumerate(self.src_formats.items()):
            cb = ttk.Checkbutton(src_format_frame, text=ext, variable=var)
            cb.pack(side=tk.LEFT, padx=(0, 10))
        
        # 目标格式选择
        dst_format_frame = ttk.Frame(format_frame)
        dst_format_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(dst_format_frame, text="目标格式:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.dst_format = tk.StringVar(value=".mp4")
        formats = [('.mp4', 'MP4'), ('.avi', 'AVI'), ('.mov', 'MOV'), 
                  ('.webm', 'WebM'), ('.mkv', 'MKV'), ('.flv', 'FLV')]
        
        for ext, name in formats:
            rb = ttk.Radiobutton(dst_format_frame, text=name, variable=self.dst_format, value=ext)
            rb.pack(side=tk.LEFT, padx=(0, 10))
        
        # 选项框架
        options_frame = ttk.LabelFrame(main_frame, text="选项")
        options_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.preserve_structure = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="保留原始目录结构", variable=self.preserve_structure).pack(anchor=tk.W, padx=5, pady=5)
        
        # 进度条
        self.progress_var = tk.IntVar()
        self.progress = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress.pack(fill=tk.X, pady=(0, 10))
        
        self.progress_label = ttk.Label(main_frame, text="准备就绪")
        self.progress_label.pack(fill=tk.X)
        
        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.convert_btn = ttk.Button(button_frame, text="开始转换", command=self.start_conversion)
        self.convert_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.cancel_btn = ttk.Button(button_frame, text="取消", command=self.cancel_conversion, state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.LEFT)
        
        # 日志区域
        log_frame = ttk.LabelFrame(main_frame, text="转换日志")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.log_text.configure(state=tk.DISABLED)
        
        # 状态栏
        self.status_var = tk.StringVar(value="准备就绪")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 转换线程
        self.converter = None
        self.conversion_thread = None
        
        # 启动UI更新循环
        self.after(100, self.update_ui)
    
    def find_default_ffmpeg(self):
        """尝试查找默认的FFmpeg路径"""
        # 首先检查当前目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 根据操作系统确定可能的文件名
        ffmpeg_names = ["ffmpeg", "ffmpeg.exe"]
        
        for name in ffmpeg_names:
            # 检查当前目录
            path = os.path.join(current_dir, name)
            if os.path.isfile(path):
                return path
            
            # 检查系统PATH
            if "PATH" in os.environ:
                for dir_path in os.environ["PATH"].split(os.pathsep):
                    full_path = os.path.join(dir_path, name)
                    if os.path.isfile(full_path):
                        return full_path
        
        return None
    
    def select_input_dir(self):
        directory = filedialog.askdirectory(title="选择输入目录")
        if directory:
            self.input_dir.set(directory)
    
    def select_output_dir(self):
        directory = filedialog.askdirectory(title="选择输出目录")
        if directory:
            self.output_dir.set(directory)
    
    def select_ffmpeg(self):
        filetypes = [("可执行文件", "*.exe")] if sys.platform == "win32" else [("所有文件", "*")]
        file_path = filedialog.askopenfilename(
            title="选择FFmpeg可执行文件",
            filetypes=filetypes
        )
        if file_path:
            self.ffmpeg_path.set(file_path)
    
    def test_ffmpeg(self):
        ffmpeg_path = self.ffmpeg_path.get().strip()
        
        if not ffmpeg_path:
            messagebox.showwarning("FFmpeg路径错误", "请指定FFmpeg可执行文件路径")
            return
        
        if not os.path.isfile(ffmpeg_path):
            messagebox.showwarning("FFmpeg路径错误", f"文件不存在: {ffmpeg_path}")
            return
        
        try:
            result = subprocess.run(
                [ffmpeg_path, '-version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            
            # 解析版本信息
            version_line = result.stdout.split('\n')[0]
            self.log_message(f"✅ FFmpeg测试成功: {version_line}")
            self.status_var.set("FFmpeg测试成功")
            
        except Exception as e:
            self.log_message(f"❌ FFmpeg测试失败: {str(e)}")
            self.status_var.set("FFmpeg测试失败")
    
    def start_conversion(self):
        # 验证输入
        input_dir = self.input_dir.get().strip()
        output_dir = self.output_dir.get().strip()
        ffmpeg_path = self.ffmpeg_path.get().strip()
        
        if not input_dir:
            messagebox.showwarning("输入错误", "请选择输入目录")
            return
        
        if not output_dir:
            messagebox.showwarning("输入错误", "请选择输出目录")
            return
        
        if not ffmpeg_path:
            messagebox.showwarning("输入错误", "请指定FFmpeg路径")
            return
        
        if not os.path.isdir(input_dir):
            messagebox.showwarning("输入错误", "输入目录不存在")
            return
        
        if not os.path.isfile(ffmpeg_path):
            messagebox.showwarning("输入错误", "FFmpeg可执行文件不存在")
            return
        
        # 检查是否至少选择了一个源格式
        selected_formats = [ext for ext, var in self.src_formats.items() if var.get()]
        if not selected_formats:
            messagebox.showwarning("输入错误", "请至少选择一个源格式")
            return
        
        # 创建输出目录（如果不存在）
        os.makedirs(output_dir, exist_ok=True)
        
        # 初始化UI状态
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state=tk.DISABLED)
        self.progress_var.set(0)
        self.progress_label.config(text="准备开始...")
        
        # 禁用UI控件
        self.convert_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.NORMAL)
        
        # 创建转换器
        self.converter = VideoConverter(
            input_dir=input_dir,
            output_dir=output_dir,
            ffmpeg_path=ffmpeg_path,
            src_formats=selected_formats,
            dst_format=self.dst_format.get(),
            preserve_structure=self.preserve_structure.get()
        )
        
        # 启动转换线程
        self.conversion_thread = threading.Thread(target=self.converter.start_conversion, daemon=True)
        self.conversion_thread.start()
    
    def cancel_conversion(self):
        if self.converter:
            self.converter.cancel()
            self.cancel_btn.config(state=tk.DISABLED)
    
    def log_message(self, message):
        """向日志区域添加消息"""
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)
    
    def update_ui(self):
        """更新UI状态"""
        # 处理日志队列
        if self.converter:
            while not self.converter.log_queue.empty():
                message = self.converter.log_queue.get()
                self.log_message(message)
        
            # 处理进度队列
            while not self.converter.progress_queue.empty():
                processed, total, message = self.converter.progress_queue.get()
                
                if total > 0:
                    progress = int((processed / total) * 100)
                    self.progress_var.set(progress)
                    self.progress_label.config(text=f"{message} - {processed}/{total} ({progress}%)")
                else:
                    self.progress_label.config(text=message)
                
                # 更新状态栏
                self.status_var.set(message)
            
            # 检查转换是否完成
            if not self.conversion_thread.is_alive():
                self.convert_btn.config(state=tk.NORMAL)
                self.cancel_btn.config(state=tk.DISABLED)
                self.converter = None
                self.conversion_thread = None
                
                # 确保进度条显示完成
                if self.progress_var.get() < 100:
                    self.progress_var.set(100)
                    self.progress_label.config(text="转换完成")
        
        # 继续调度更新
        self.after(100, self.update_ui)


if __name__ == "__main__":
    app = VideoConverterApp()
    app.mainloop()