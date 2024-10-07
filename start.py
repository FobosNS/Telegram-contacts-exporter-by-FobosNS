import wx
from datetime import datetime
from telethon import functions
from telethon.sync import TelegramClient
from telethon.errors import SessionPasswordNeededError
import webbrowser
import csv


# Получаем текущее время для имени файла
now_str = f"{datetime.now()}".replace(" ", "_").replace(":", ".")


class TelegramConnection:
    """
        Custom TelegramClient with task to get the contact list in Telegram
    """
    def __init__(self, api_id, api_hash, phone):
        self.__client = TelegramClient('Contacts_Exporter', api_id=api_id, api_hash=api_hash)
        self.phone = phone

    def connect(self):
        self.__client.connect()
        if not self.__client.is_user_authorized():
            self.__client.send_code_request(self.phone)
            return False  # Требуется ввод кода подтверждения
        return True

    def confirm_code(self, code):
        try:
            self.__client.sign_in(self.phone, code)
            return True
        except SessionPasswordNeededError:
            return False  # Требуется ввод облачного пароля
        except Exception as e:
            raise e

    def confirm_password(self, password):
        try:
            self.__client.sign_in(password=password)
            return True
        except Exception as e:
            raise e

    def disconnect(self):
        self.__client.log_out()

    def get_contacts(self) -> list:
        return self.__client(functions.contacts.GetContactsRequest(hash=0)).__dict__['users']


def save_to_file(filename, contact_objects, file_format='txt'):
    count = 0
    if file_format == 'txt':
        with open(filename, 'w', encoding='utf-8') as f:
            for contact in contact_objects:
                first_name = contact.first_name if contact.first_name else ""
                last_name = contact.last_name if contact.last_name else ""
                line = f"{first_name} {last_name}".strip()
                if contact.phone:
                    line += f" - {contact.phone}"
                line += "\n"
                f.write(line)
                count += 1
    elif file_format == 'csv':
        with open(filename, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['First Name', 'Last Name', 'Phone'])
            for contact in contact_objects:
                first_name = contact.first_name if contact.first_name else ""
                last_name = contact.last_name if contact.last_name else ""
                phone = contact.phone if contact.phone else ""
                writer.writerow([first_name, last_name, phone])
                count += 1
    elif file_format == 'vcf':
        with open(filename, 'w', encoding='utf-8') as f:
            for contact in contact_objects:
                first_name = contact.first_name if contact.first_name else ""
                last_name = contact.last_name if contact.last_name else ""
                phone = contact.phone if contact.phone else ""
                if first_name or last_name or phone:
                    f.write("BEGIN:VCARD\n")
                    f.write("VERSION:3.0\n")
                    if first_name or last_name:
                        f.write(f"N:{last_name};{first_name};;;\n")
                        f.write(f"FN:{first_name} {last_name}\n")
                    if phone:
                        f.write(f"TEL;TYPE=CELL:{phone}\n")
                    f.write("END:VCARD\n")
                    count += 1
    return count


class MainFrame(wx.Frame):
    def __init__(self, *args, **kw):
        super(MainFrame, self).__init__(*args, **kw)

        self.panel = wx.Panel(self)

        # Создаем вертикальный sizer для размещения элементов
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Поля для ввода API ID, API Hash и номера телефона
        hbox1 = wx.BoxSizer(wx.HORIZONTAL)
        hbox1.Add(wx.StaticText(self.panel, label="API ID:"), flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        self.api_id_field = wx.TextCtrl(self.panel)
        hbox1.Add(self.api_id_field, proportion=1)
        vbox.Add(hbox1, flag=wx.EXPAND | wx.ALL, border=10)

        hbox2 = wx.BoxSizer(wx.HORIZONTAL)
        hbox2.Add(wx.StaticText(self.panel, label="API Hash:"), flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        self.api_hash_field = wx.TextCtrl(self.panel)
        hbox2.Add(self.api_hash_field, proportion=1)
        vbox.Add(hbox2, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)

        hbox3 = wx.BoxSizer(wx.HORIZONTAL)
        hbox3.Add(wx.StaticText(self.panel, label="Номер телефону (380...):"), flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        self.phone_field = wx.TextCtrl(self.panel)
        hbox3.Add(self.phone_field, proportion=1)
        vbox.Add(hbox3, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)

        # Кнопка для подключения
        self.connect_btn = wx.Button(self.panel, label="Підключитись до аккаунту Telegram")
        vbox.Add(self.connect_btn, flag=wx.EXPAND | wx.ALL, border=10)
        self.connect_btn.Bind(wx.EVT_BUTTON, self.on_connect)

        # Кнопка для экспорта
        self.export_btn = wx.Button(self.panel, label="Експортувати контакти")
        vbox.Add(self.export_btn, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)
        self.export_btn.Bind(wx.EVT_BUTTON, self.on_export)
        self.export_btn.Disable()

        # Кнопка для завершения сеанса
        self.disconnect_btn = wx.Button(self.panel, label="Завершити сесію експорту контактів")
        vbox.Add(self.disconnect_btn, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)
        self.disconnect_btn.Bind(wx.EVT_BUTTON, self.on_disconnect)
        self.disconnect_btn.Disable()

        # Раскрывающийся список для выбора формата сохранения
        hbox_format = wx.BoxSizer(wx.HORIZONTAL)
        hbox_format.Add(wx.StaticText(self.panel, label="Формат збереження:"), flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        self.format_choice = wx.Choice(self.panel, choices=["txt", "csv", "vcf"])
        self.format_choice.SetSelection(0)  # Устанавливаем по умолчанию txt
        hbox_format.Add(self.format_choice, proportion=1)
        vbox.Add(hbox_format, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)

        # Поле для статуса
        self.status_text = wx.StaticText(self.panel, label="")
        vbox.Add(self.status_text, flag=wx.EXPAND | wx.ALL, border=10)

        # Вместо HyperlinkCtrl - кнопка с открытием браузера
        self.api_link_btn = wx.Button(self.panel, label="Отримати API ID та API Hash")
        self.api_link_btn.Bind(wx.EVT_BUTTON, self.on_open_link)
        vbox.Add(self.api_link_btn, flag=wx.ALIGN_CENTER | wx.ALL, border=10)

        self.panel.SetSizer(vbox)

        self.contacts = []
        self.client = None

    def on_open_link(self, event):
        webbrowser.open("https://my.telegram.org/auth")

    def on_connect(self, event):
        try:
            api_id = self.api_id_field.GetValue().strip()
            api_hash = self.api_hash_field.GetValue().strip()
            phone = self.phone_field.GetValue().strip()

            if not api_id or not api_hash or not phone:
                self.status_text.SetLabel("Будь ласка, введіть API ID, API Hash та номер телефону.")
                return

            if not phone.startswith("380"):
                self.status_text.SetLabel("Номер телефону повинен починатися з 380.")
                return

            self.client = TelegramConnection(api_id, api_hash, phone)
            if not self.client.connect():
                self.status_text.SetLabel("Введіть код підтвердження з Telegram.")
                self.ask_for_code()
            else:
                self.load_contacts()

        except Exception as e:
            self.status_text.SetLabel(f"Помилка: {str(e)}")

    def ask_for_code(self):
        code_dialog = wx.TextEntryDialog(self, "Введіть код підтвердження, який ви отримали:", "Код підтвердження")
        if code_dialog.ShowModal() == wx.ID_OK:
            code = code_dialog.GetValue().strip()
            try:
                if not self.client.confirm_code(code):
                    self.ask_for_password()  # Запрос пароля, если требуется двухфакторная аутентификация
                else:
                    self.load_contacts()
            except Exception as e:
                self.status_text.SetLabel(f"Помилка при перевірці коду: {str(e)}")

    def ask_for_password(self):
        password_dialog = wx.PasswordEntryDialog(self, "Введіть ваш хмарний пароль:", "Хмарний Пароль")
        if password_dialog.ShowModal() == wx.ID_OK:
            password = password_dialog.GetValue().strip()
            try:
                if self.client.confirm_password(password):
                    self.load_contacts()
            except Exception as e:
                self.status_text.SetLabel(f"Помилка при перевірці пароля: {str(e)}")

    def load_contacts(self):
        try:
            self.contacts = self.client.get_contacts()
            self.status_text.SetLabel(f"У вас {len(self.contacts)} контактів.")
            self.export_btn.Enable()
            self.disconnect_btn.Enable()
        except Exception as e:
            self.status_text.SetLabel(f"Помилка при завантаженні контактів: {str(e)}")

    def on_export(self, event):
        # Получаем выбранный формат файла
        selection = self.format_choice.GetStringSelection()
        file_wildcard = f"{selection.upper()} файли (*.{selection})|*.{selection}"
        
        with wx.FileDialog(self, "Зберегти контакти", wildcard=file_wildcard,
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return  # Пользователь закрыл диалог

            path = file_dialog.GetPath()

            # Меняем расширение файла в зависимости от выбора
            if not path.lower().endswith(f".{selection}"):
                path += f".{selection}"

            try:
                count = save_to_file(path, self.contacts, file_format=selection)
                self.status_text.SetLabel(f"Експортовано {count} контактів до {path}")
            except Exception as e:
                self.status_text.SetLabel(f"Помилка при збереженні файлу: {str(e)}")

    def on_disconnect(self, event):
        if self.client:
            try:
                self.client.disconnect()
                self.status_text.SetLabel("Успішний вихід.")
                self.export_btn.Disable()
                self.disconnect_btn.Disable()
            except Exception as e:
                self.status_text.SetLabel(f"Помилка при виході: {str(e)}")


class MyApp(wx.App):
    def OnInit(self):
        self.frame = MainFrame(None, title="Telegram Contacts Exporter by FobosNS v.1.0", size=(500, 400))
        self.frame.Show()
        return True


if __name__ == '__main__':
    app = MyApp()
    app.MainLoop()
