import sys
import configparser
import requests
import time
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpacerItem, QSizePolicy, QInputDialog, QMessageBox
from PyQt5.QtGui import QPainter, QColor, QPixmap, QIcon
from PyQt5.QtCore import QSize, Qt, QThread, pyqtSignal


#questo codice gnera un UX x gestire streaming della parte server
# se premiamo pulsante start manda un set con rtmp=1
#se premiamo il pulsante stop manda un set con rtmp=0
#se server manda un zero, da un messaggio interrotto

class SetApiThread(QThread):
    """
    Thread for sending SET requests to update rtmp_enable value.
    """
    response_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, ip, rtmp_enable):
        QThread.__init__(self)
        self.ip = ip
        self.rtmp_enable = rtmp_enable

    def run(self):
        try:
            url = f"http://{self.ip}:8080/set_ctl?type=hdmi_main&rtmp_enable={self.rtmp_enable}"
            response = requests.get(url)
            self.response_signal.emit(response.text)
        except Exception as e:
            self.error_signal.emit(str(e))

class GetApiThread(QThread):
    response_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    update_button_signal = pyqtSignal(bool)  # True if streaming, False otherwise
    update_led_signal = pyqtSignal(bool)     # True if LED on, False otherwise

    def __init__(self, ip, rtmp_enable, continuous=True):
        super().__init__()
        self.ip = ip
        self.rtmp_enable = rtmp_enable
        self.running = True
        self.continuous = continuous  # Add this line


    def run(self):
        if not self.continuous:
            self.check_once()
        else:
            self.check_continuously()

    def check_once(self):
        """
        Perform a single check to see if the RTMP stream is active.
        Update the streaming button and LED indicator accordingly.
        """
        try:
            url = f"http://{self.ip}:8080/get_ctl?type=hdmi_main"
            response = requests.get(url, timeout=0.5)
            if self.is_rtmp_disabled(response.text):
                self.rtmp_enable = 0

            else:
                self.response_signal.emit(response.text)

        except Exception as e:
            self.error_signal.emit(str(e))

    def check_continuously(self):
        """
        Continuously check if the RTMP stream is active.
        """
        while self.running:
            if self.rtmp_enable == 0:
                break  # Stop if rtmp_enable is 0
            self.check_once()
            time.sleep(1)

    def run(self):
        self.check_continuously()


    def is_rtmp_disabled(self, response_text):
        # Add logic to determine if the response indicates rtmp_enable is set to 0
        # Example: return 'rtmp_enable=0' in response_text
        pass

    def set_rtmp_enable(self, value):
        self.rtmp_enable = value

    def stop(self):
        self.running = False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Flag to track streaming state
        self.is_streaming = False

        ##main window
        self.setMinimumSize(QSize(451, 410))  # Window size
        self.setWindowTitle("Interfaccia di Streaming RTMP")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)


        # Layout for the LED indicator
        top_layout = QHBoxLayout()
        top_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.led_indicator = QLabel()
        self.update_led_indicator('white')
        top_layout.addWidget(self.led_indicator)
        main_layout.addLayout(top_layout)

        # Label for streaming status
        self.streaming_status_label = QLabel("")
        self.streaming_status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        font = self.streaming_status_label.font()
        font.setPointSize(18)  # Set your desired font size
        self.streaming_status_label.setFont(font)
        main_layout.addWidget(self.streaming_status_label)


        # Layout for the streaming button
        middle_layout = QHBoxLayout()
        self.start_rtmp_button = QPushButton("Start RTMP \nStreaming")
        self.start_rtmp_button.setFixedSize(200, 250)
        self.start_rtmp_button.setStyleSheet("QPushButton { background-color: #FFFFFF; font-size: 20px; color: #FFFFFF; }")
        self.start_rtmp_button.clicked.connect(self.start_streaming)
        middle_layout.addWidget(self.start_rtmp_button)
        middle_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        main_layout.addLayout(middle_layout)


        #setting button
        self.settings_button = QPushButton(central_widget)
        self.settings_button.setIcon(QIcon(r'C:\Users\Utente\Downloads\Immagine2.png'))  # Set the icon image
        self.settings_button.setIconSize(QSize(50, 50))  # Set the icon size
        self.settings_button.setGeometry(371, 330, 50, 50)  # position and size of the button
        self.settings_button.setStyleSheet("QPushButton { background: transparent; }")
        self.settings_button.clicked.connect(self.open_settings)
        self.settings_button.setCursor(Qt.PointingHandCursor)  # Change cursor on hover
        

        # Initialize configuration
        config = configparser.ConfigParser()
        config.read('config.ini')
        ip = config.get('Settings', 'IP', fallback='127.0.0.1')
        rtmp_enable = int(config.get('Settings', 'rtmp_enable', fallback='0'))

        self.check_server_status_on_start(ip)


        # Initialize the GetApiThread (to monitor streaming status)
        self.get_thread = GetApiThread(ip, rtmp_enable)
        self.get_thread.response_signal.connect(self.handle_api_response)
        self.get_thread.error_signal.connect(self.handle_api_error)

        # Attribute to track if IP has been set
        self.ip_set = False


    def disable_main_window_components(self):
        """ Turn off main window components visually. """
        # Turn off the start RTMP button
        self.start_rtmp_button.setEnabled(False)
        

    def enable_main_window_components(self):
        """ Enable all main window components. """
        self.start_rtmp_button.setEnabled(True)
        


    def get_ip_address(self):
        """
        Fetches the IP address from the config file or prompts the user to enter it.
        """
        config = configparser.ConfigParser()
        config.read('config.ini')
        ip = config.get('Settings', 'IP', fallback='')

        if not ip:
            ip, ok = QInputDialog.getText(self, 'Impostazioni', 'Inserisci il tuo IP:')
            if ok and ip and self.is_valid_ip(ip):
                self.save_ip_to_config(ip)
            else:
                QMessageBox.warning(self, "Errore", "Indirizzo IP non valido o non inserito.")
                sys.exit(1)  # Exit the application if no valid IP is provided

        return ip
    

    def check_server_status_on_start(self, ip):
            
            #if not self.is_streaming:
            self.disable_main_window_components()
            # Create a temporary thread for checking the server status
            temp_thread = GetApiThread(ip, rtmp_enable=1)
            print("Checking server status...")
            temp_thread.response_signal.connect(self.handle_initial_status)
            temp_thread.error_signal.connect(self.handle_api_error)
            temp_thread.check_once()  # Custom method for one-time check


    def handle_initial_status(self, response):
        # Update LED based on initial server status
        if response == '1':
            self.update_led_indicator('green')
            self.streaming_status_label.setText("Sto registrando")
            self.start_rtmp_button.setText("Stop RTMP \nStreaming")
            self.start_rtmp_button.setStyleSheet("QPushButton { background-color: #D3D3D3; font-size: 20px; color: #FFFFFF; }")  # Set button background to grey
            self.settings_button.setEnabled(False)
            self.is_streaming = True
            self.enable_main_window_components()

        else:
            self.update_led_indicator('grey')
            self.start_rtmp_button.setText("Start RTMP \nStreaming")
            self.start_rtmp_button.setStyleSheet("QPushButton { background-color: #D3D3D3; font-size: 20px; color: #FFFFFF; }")  # Set button background to grey
            self.enable_main_window_components()

    def update_led_indicator(self, color):
        size = 100  # Size for the LED indicator
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(color))
        painter.drawEllipse(0, 0, size, size)
        painter.end()
        self.led_indicator.setPixmap(pixmap)


    def start_streaming(self):
        config = configparser.ConfigParser()
        config.read('config.ini')
        ip = config.get('Settings', 'IP', fallback='')

        if not ip:
            self.display_error_message("Inserire Ip")
            return

        if not self.is_streaming:
            # Start streaming logic
            self.set_thread = SetApiThread(ip, rtmp_enable=1)
            self.set_thread.response_signal.connect(self.handle_api_response)
            self.set_thread.error_signal.connect(self.handle_api_error)
            self.set_thread.start()

            self.get_thread = GetApiThread(ip, rtmp_enable=1)
            self.get_thread.response_signal.connect(self.handle_api_response)
            self.get_thread.error_signal.connect(self.handle_api_error)
            self.get_thread.start()

            self.update_led_indicator('green')
            self.streaming_status_label.setText("Sto registrando")
            self.start_rtmp_button.setText("Stop RTMP \nStreaming")
            self.is_streaming = True
            print("Started streaming")
            self.settings_button.setEnabled(False)
            #self.disable_main_window_components()
        else:
            # Stop streaming logic
            self.stop_streaming(ip)


    def stop_streaming(self, ip):
        # Method to handle the stop streaming button
        if self.is_streaming:
            # Start the SET thread to disable streaming
            self.set_thread = SetApiThread(ip, rtmp_enable=0)
            self.set_thread.response_signal.connect(self.handle_api_response)
            self.set_thread.error_signal.connect(self.handle_api_error)
            self.set_thread.start()


            self.set_thread.response_signal.disconnect()
            self.set_thread.error_signal.disconnect()
            self.get_thread.response_signal.disconnect()
            self.get_thread.error_signal.disconnect()

            self.get_thread.stop()
            self.get_thread.wait()

            self.update_led_indicator('grey')
            self.streaming_status_label.setText("")
            self.start_rtmp_button.setText("Start RTMP \nStreaming")
            self.is_streaming = False
            print("Stopped streaming")
            self.settings_button.setEnabled(True)

            # Stop the GET thread
            self.get_thread.stop()
            


    def handle_api_error(self, error_message):
        # Handle connection errors
        self.display_error_message("Errore: Non collegato al server")
        self.settings_button.setEnabled(True)
        self.enable_main_window_components()
        self.start_rtmp_button.setText("Start RTMP \nStreaming")
        self.start_rtmp_button.setStyleSheet("QPushButton { background-color: #D3D3D3; font-size: 20px; color: #FFFFFF; }")

    def display_error_message(self, message):
        self.streaming_status_label.setText(message)
        self.update_led_indicator('grey')
        self.start_rtmp_button.setText("Start RTMP \nStreaming")
        self.is_streaming = False


    def handle_api_response(self, response):
        # This method monitors by get the server
        if response == '0':
            self.update_led_indicator('red')
            self.streaming_status_label.setText("La registrazione è interrotta")
            self.start_rtmp_button.setText("Stop RTMP \nStreaming")
            self.get_thread.stop()
            self.get_thread.wait()
            self.settings_button.setEnabled(False)
        else:
            self.update_led_indicator('green')
            self.streaming_status_label.setText("Sto registrando")
            self.start_rtmp_button.setText("Stop RTMP \nStreaming")
            self.is_streaming = True
            self.settings_button.setEnabled(False)

    def open_settings(self):
        config = configparser.ConfigParser()
        config.read('config.ini')
        current_ip = config.get('Settings', 'IP', fallback='')

        ip, ok = QInputDialog.getText(self, 'Impostazioni', 'Inserisci il tuo IP:', text=current_ip)
        if ok and ip:
            if self.is_valid_ip(ip):
                self.save_ip_to_config(ip)
                self.ip_set = True  # Set flag to True when a valid IP is set
                
            else:
                QMessageBox.warning(self, "Errore", "Indirizzo IP non valido.")

    def save_ip_to_config(self, ip):
        config = configparser.ConfigParser()
        config['Settings'] = {'IP': ip}
        with open('config.ini', 'w') as configfile:
            config.write(configfile)

    def is_valid_ip(self, ip):
        try:
            parts = ip.split(".")
            if len(parts) != 4:
                return False
            for item in parts:
                if not 0 <= int(item) <= 255:
                    return False
            return True
        except ValueError:
            # A part of the IP address is not a number
            return False

if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())