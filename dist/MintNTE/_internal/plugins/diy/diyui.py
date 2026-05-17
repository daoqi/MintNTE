"""
diyui.py - 可视化动作编辑器（基于 tkinter）
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import threading
from diycore import ActionRunner

# ---------- 动作类型定义 ----------
ACTION_TYPES = {
    "wait":      {"name": "延时", "params": {"value": "1.0"}},
    "key":       {"name": "按键", "params": {"window": "异环", "key": "0x46"}},
    "click":     {"name": "点击", "params": {"window": "异环", "x": "100", "y": "100"}},
    "find_image":{"name": "找图", "params": {"path": "", "window": "异环", "confidence": "0.8",
                                            "offset_x": "0", "offset_y": "0", "do_click": "False"}},
    "for_start": {"name": "For循环开始", "params": {"count": "3"}},
    "while_start":{"name":"While循环开始", "params": {"condition": "True"}},
    "loop_end":  {"name": "循环结束", "params": {}},
    "exit_loop": {"name": "退出循环", "params": {}}
}

class ActionEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("🎣 异环自动化动作编辑器")
        self.actions = []          # 当前方案动作列表
        self.runner_thread = None
        self.stop_event = threading.Event()

        # ----- 左侧：动作列表 -----
        left_frame = tk.Frame(root)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        tk.Label(left_frame, text="动作序列").pack(anchor=tk.W)
        self.listbox = tk.Listbox(left_frame, width=40, height=20)
        self.listbox.pack(fill=tk.BOTH, expand=True)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        btn_frame = tk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=2)
        tk.Button(btn_frame, text="上移", command=self.move_up).pack(side=tk.LEFT)
        tk.Button(btn_frame, text="下移", command=self.move_down).pack(side=tk.LEFT)
        tk.Button(btn_frame, text="删除", command=self.delete_action).pack(side=tk.LEFT)

        # ----- 右侧：参数面板 + 添加按钮 -----
        right_frame = tk.Frame(root)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 动作添加按钮
        add_frame = tk.LabelFrame(right_frame, text="添加动作")
        add_frame.pack(fill=tk.X, pady=5)
        for atype, info in ACTION_TYPES.items():
            tk.Button(add_frame, text=info["name"],
                      command=lambda t=atype: self.add_action(t)).pack(fill=tk.X, pady=1)

        # 参数编辑区
        param_frame = tk.LabelFrame(right_frame, text="参数编辑")
        param_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.param_entries = {}   # 动态生成的输入控件
        self.param_frame = param_frame

        # 图片路径选择（专门给找图用）
        self.img_path_var = tk.StringVar()

        # 全局控制按钮
        ctrl_frame = tk.Frame(right_frame)
        ctrl_frame.pack(fill=tk.X, pady=5)
        tk.Button(ctrl_frame, text="▶ 运行", bg="green", fg="white", command=self.start_run).pack(side=tk.LEFT, padx=2)
        tk.Button(ctrl_frame, text="⏹ 停止", bg="red", fg="white", command=self.stop_run).pack(side=tk.LEFT, padx=2)
        tk.Button(ctrl_frame, text="💾 保存方案", command=self.save_plan).pack(side=tk.LEFT, padx=2)
        tk.Button(ctrl_frame, text="📂 加载方案", command=self.load_plan).pack(side=tk.LEFT, padx=2)

        self.status_var = tk.StringVar(value="就绪")
        tk.Label(ctrl_frame, textvariable=self.status_var, fg="blue").pack(side=tk.LEFT, padx=10)

    # ---------- 动作管理 ----------
    def add_action(self, atype):
        action = {"type": atype, "params": dict(ACTION_TYPES[atype]["params"])}
        self.actions.append(action)
        self.refresh_list()
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(tk.END)

    def delete_action(self):
        sel = self.listbox.curselection()
        if sel:
            idx = sel[0]
            del self.actions[idx]
            self.refresh_list()

    def move_up(self):
        sel = self.listbox.curselection()
        if sel and sel[0] > 0:
            idx = sel[0]
            self.actions[idx], self.actions[idx-1] = self.actions[idx-1], self.actions[idx]
            self.refresh_list()
            self.listbox.selection_set(idx-1)

    def move_down(self):
        sel = self.listbox.curselection()
        if sel and sel[0] < len(self.actions)-1:
            idx = sel[0]
            self.actions[idx], self.actions[idx+1] = self.actions[idx+1], self.actions[idx]
            self.refresh_list()
            self.listbox.selection_set(idx+1)

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        for act in self.actions:
            name = ACTION_TYPES[act["type"]]["name"]
            extra = ""
            if act["type"] == "key":
                extra = f" (键:{act['params'].get('key','')})"
            elif act["type"] == "click":
                extra = f" ({act['params'].get('x','')},{act['params'].get('y','')})"
            elif act["type"] == "find_image":
                p = act['params'].get('path','')
                extra = f" ({p.split('/')[-1] if p else '未选'})"
            self.listbox.insert(tk.END, name + extra)

    def on_select(self, event):
        """选中动作时刷新参数面板"""
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        action = self.actions[idx]
        # 清空旧控件
        for widget in self.param_frame.winfo_children():
            widget.destroy()
        self.param_entries.clear()

        params = action["params"]
        row = 0
        for key, val in params.items():
            tk.Label(self.param_frame, text=key).grid(row=row, column=0, sticky=tk.W)
            if key == "path":
                # 图片选择
                entry = tk.Entry(self.param_frame, textvariable=self.img_path_var, width=20)
                self.img_path_var.set(val)
                entry.grid(row=row, column=1)
                tk.Button(self.param_frame, text="浏览",
                          command=lambda k=key: self.browse_image(k, action)).grid(row=row, column=2)
            else:
                var = tk.StringVar(value=val)
                entry = tk.Entry(self.param_frame, textvariable=var, width=20)
                entry.grid(row=row, column=1)
                self.param_entries[key] = var
            row += 1

        tk.Button(self.param_frame, text="应用参数",
                  command=lambda a=action: self.apply_params(a)).grid(row=row, column=0, columnspan=2, pady=5)

    def browse_image(self, key, action):
        path = filedialog.askopenfilename(filetypes=[("图片文件", "*.png *.jpg *.jpeg")])
        if path:
            action["params"]["path"] = path
            self.img_path_var.set(path)
            self.refresh_list()

    def apply_params(self, action):
        """从界面读取参数并保存到动作"""
        for key, var in self.param_entries.items():
            action["params"][key] = var.get()
        # 特殊处理 path
        if "path" in action["params"]:
            action["params"]["path"] = self.img_path_var.get()
        self.refresh_list()
        self.status_var.set("参数已更新")

    # ---------- 运行与停止 ----------
    def start_run(self):
        if self.runner_thread and self.runner_thread.is_alive():
            messagebox.showwarning("运行中", "当前已有任务在运行")
            return
        self.stop_event.clear()
        self.runner_thread = threading.Thread(target=self._run, daemon=True)
        self.runner_thread.start()

    def _run(self):
        runner = ActionRunner(self.actions, self.stop_event,
                              status_callback=lambda msg: self.status_var.set(msg))
        try:
            runner.run()
        except Exception as e:
            self.status_var.set(f"错误: {e}")

    def stop_run(self):
        self.stop_event.set()
        self.status_var.set("正在停止...")

    def save_plan(self):
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            filetypes=[("JSON 文件", "*.json")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.actions, f, ensure_ascii=False, indent=2)
            self.status_var.set(f"已保存至 {path}")

    def load_plan(self):
        path = filedialog.askopenfilename(filetypes=[("JSON 文件", "*.json")])
        if path:
            with open(path, "r", encoding="utf-8") as f:
                self.actions = json.load(f)
            self.refresh_list()
            self.status_var.set(f"已加载 {path}")

# ---------- 启动入口 ----------
def start_gui():
    root = tk.Tk()
    app = ActionEditor(root)
    root.mainloop()

if __name__ == "__main__":
    start_gui()