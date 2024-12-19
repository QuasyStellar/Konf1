import os
import zipfile
import json
import tkinter as tk
from tkinter import scrolledtext


def add_folder(path, folder_name):
    return os.path.join(path, folder_name)


def remove_last_folder(path):
    return os.path.dirname(path)


class Emulator:

    def __init__(self, config_path):
        """
        Конструктор класса Emulator. Инициализирует параметры из конфигурационного файла.

        :param config_path: Путь к JSON файлу конфигурации
        """
        with open(config_path, "r") as config_file:
            config = json.load(config_file)

        self.username = config["username"]
        self.hostname = "emulator"
        self.current_directory = "/"  # Текущая директория (начинаем с корня '/')
        self.zip_path = config["zip_path"]
        self.start_script_path = config.get("start_script", None)
        self.file_system = {}  # Словарь для хранения распакованных файлов и папок
        self._load_file_system()  # Распаковываем архив в память

        # Выполнение стартового скрипта, если он указан
        if self.start_script_path:
            self._execute_start_script()

    def _load_file_system(self):
        """
        Метод для распаковки ZIP архива в виртуальную файловую систему.
        """
        if zipfile.is_zipfile(self.zip_path):
            with zipfile.ZipFile(self.zip_path, "r") as zip_ref:
                for file in zip_ref.namelist():
                    normalized_path = file.lstrip("/")
                    self.file_system[normalized_path] = zip_ref.read(file).decode(
                        "utf-8"
                    )
        else:
            print("Error: provided file is not a ZIP archive.")

    def _execute_start_script(self):
        """
        Метод для выполнения команд из стартового скрипта.
        """
        if os.path.exists(self.start_script_path):
            with open(self.start_script_path, "r") as script_file:
                commands = script_file.readlines()
                for command in commands:
                    print(f"Executing: {command.strip()}")
                    self.execute_command(command.strip())

    def _get_prompt_directory(self):
        """Метод для получения текущей директории для отображения в prompt."""
        return self.current_directory if self.current_directory != "/" else "/"

    def ls(self, directory=None):
        """
        Команда 'ls' выводит список файлов и папок в указанной директории (или текущей, если аргумент не передан).
        """
        if directory:
            path = os.path.join(self.current_directory, directory).lstrip("/")
        else:
            path = self.current_directory.lstrip("/")

        output = []
        for file in self.file_system:
            if file.startswith(path):
                relative_path = file[len(path) :].strip("/")
                if "/" not in relative_path and relative_path:
                    output.append(relative_path)

        if not output:
            return "Directory is empty."
        return "\n".join(output)

    def cd(self, path):
        """
        Команда 'cd' позволяет перемещаться между директориями.

        :param path: Путь к новой директории
        """
        if path == "..":
            if self.current_directory != "/":
                self.current_directory = (
                    remove_last_folder(self.current_directory.rstrip("/")) + "/"
                )
        else:
            new_directory = os.path.join(self.current_directory, path).lstrip("/")
            if any(f.startswith(new_directory) for f in self.file_system.keys()):
                self.current_directory = new_directory.rstrip("/") + "/"
            else:
                return "Error: directory not found."
        return ""

    def cp(self, source, destination):
        """
        Команда 'cp' копирует содержимое файла в новый путь.

        :param source: Путь к исходному файлу
        :param destination: Путь к новому файлу
        """
        source_path = os.path.join(self.current_directory, source).lstrip("/")

        destination_path = os.path.join(self.current_directory, destination).lstrip("/")
        print(source_path, destination_path, self.file_system)
        if source_path in self.file_system:
            self.file_system[destination_path + source] = self.file_system[source_path]
            print(self.file_system[destination_path], self.file_system[source_path])
            return f"File '{source}' copied to '{destination}'."
        return "Error: source file not found."

    def tree(self, path="", prefix=""):
        """
        Команда 'tree' выводит дерево каталогов и файлов.

        :param path: Текущая директория
        :param prefix: Префикс для форматирования вывода
        """
        path = os.path.join(self.current_directory, path).rstrip("/")
        output = []

        # Сортируем записи, чтобы сначала были директории, потом файлы
        entries = sorted(
            [file for file in self.file_system if file.startswith(path)],
            key=lambda x: (x.count("/"), x),
        )

        seen_dirs = set()

        for entry in entries:
            relative_entry = entry[len(path) :].strip("/")

            if "/" in relative_entry:
                subdir = relative_entry.split("/")[0]
                if subdir not in seen_dirs:
                    seen_dirs.add(subdir)
                    output.append(f"{prefix}|-- {subdir}/")
                    output.extend(
                        self.tree(os.path.join(path, subdir), prefix + "|   ")
                    )
            else:
                output.append(f"{prefix}|-- {relative_entry}")

        return "\n".join(output)

    def execute_command(self, command):
        """Метод для выполнения команд."""
        if command.startswith("ls"):
            args = command.split(" ")
            return self.ls(args[1] if len(args) > 1 else None)
        elif command.startswith("cd "):
            return self.cd(command.split(" ")[1])
        elif command.startswith("cp "):
            args = command.split(" ")
            if len(args) == 3:
                return self.cp(args[1], args[2])
            return "Error: invalid arguments for 'cp'."
        elif command == "tree":
            return self.tree()
        elif command == "exit":
            return "Exiting emulator..."
        return "Unknown command."


class EmulatorGUI:

    def __init__(self, emulator):
        self.emulator = emulator

        # Создаем главное окно
        self.window = tk.Tk()
        self.window.title("Linux Emulator")
        self.window.configure(bg="black")
        self.window.minsize(900, 500)

        # Создаем область вывода
        self.output_text = scrolledtext.ScrolledText(
            self.window,
            width=80,
            height=20,
            bg="black",
            fg="green",
            state="disabled",
            font=("Consolas", 12),
        )
        self.output_text.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # Область для отображения текущего хоста и директории
        self.host_display = tk.Label(
            self.window,
            text=f"{emulator.username}@{emulator.hostname}:{emulator._get_prompt_directory()}$",
            bg="black",
            fg="green",
            font=("Consolas", 12),
            anchor="w",
        )
        self.host_display.grid(row=2, column=0, sticky="w", padx=10, pady=5)

        # Поле для ввода команд
        self.command_entry = tk.Entry(
            self.window,
            width=80,
            bg="black",
            fg="green",
            font=("Consolas", 12),
            insertbackground="green",
        )
        self.command_entry.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        self.command_entry.bind("<Return>", self.run_command)

        # Настройка растягивания
        self.window.grid_rowconfigure(0, weight=1)
        self.window.grid_rowconfigure(1, weight=0)
        self.window.grid_rowconfigure(2, weight=0)
        self.window.grid_columnconfigure(0, weight=1)

        self.window.mainloop()

    def run_command(self, event):
        """Обработчик ввода команды и её выполнения."""
        command = self.command_entry.get()
        self.output_text.config(state="normal")
        self.output_text.insert(
            tk.END,
            f"{self.emulator.username}@{self.emulator.hostname}:{self.emulator._get_prompt_directory()}$ {command}\n",
        )
        self.output_text.config(state="disabled")
        self.command_entry.delete(0, tk.END)

        output = self.emulator.execute_command(command)

        if command == "exit":
            self.window.destroy()

        self.host_display.config(
            text=f"{self.emulator.username}@{self.emulator.hostname}:{self.emulator._get_prompt_directory()}$"
        )
        self.output_text.config(state="normal")
        self.output_text.insert(tk.END, f"{output}\n")
        self.output_text.config(state="disabled")
        self.output_text.yview(tk.END)


# Основной код
if __name__ == "__main__":
    config_path = "config.json"
    emulator = Emulator(config_path)
    EmulatorGUI(emulator)
