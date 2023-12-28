
import configparser

import logging
from logging.handlers import RotatingFileHandler

import threading
import time

import os
import sys

import tkinter as Tk
from PIL import Image, ImageTk

import vlc

from dirsync import sync


_isWindows = sys.platform.startswith('win')
_isLinux   = sys.platform.startswith('linux')

# Define consants for configuration
MOUTN_PATH = ''
LOCAL_FILE_PATH = ''
ALLOWED_EXTENSIONS = ''
WATERMARK_FILE = ''



class VLCPlaylistManager:
    '''
    Class to handle the python-vlc lib.
    This class initializes the player, adds files to playlist, removes files from playlists and
    starts the player.

    Args:
        None
    Attributes:
        None
    '''
    def __init__(self):
        # VLC player
        self.WATERMARK_PATH = "watermark/"

        args = []
        # if (os.path.isfile(self.WATERMARK_PATH)):
            # watermark_options = f"logo-overlay={self.WATERMARK_PATH}"
            # vlc --video-filter "logo{file=cone.png,opacity=128}" somevideo.avi
            # args.append(f"logo{{file={self.WATERMARK_PATH},opacity=128}}")
            # args.append(f"--logo-file={self.WATERMARK_PATH}")
            # args.append(f"logo-overlay={self.WATERMARK_PATH}")
        if _isLinux:
            args.append('--vout=qt')
        print(args)
        self.instance = vlc.Instance(args)
        # self.player = self.instance.media_player_new()

        self.list_player = self.instance.media_list_player_new()
        self.list_player.set_playback_mode(vlc.PlaybackMode.loop)
        self.list = self.instance.media_list_new()
        self.list_player.set_media_list(self.list)
        # self.list_player.set_media_player(self.player)

        self.media_player = self.list_player.get_media_player()

        if (WATERMARK_FILE != ''):
            watermark_path = self.WATERMARK_PATH + WATERMARK_FILE

            self.media_player.video_set_logo_int(vlc.VideoLogoOption.logo_enable, 1)
            self.media_player.video_set_logo_string(vlc.VideoLogoOption.logo_file, watermark_path)

            self.media_player.video_set_logo_int(vlc.VideoLogoOption.logo_delay, -1)
            self.media_player.video_set_logo_int(vlc.VideoLogoOption.logo_x, 10)
            self.media_player.video_set_logo_int(vlc.VideoLogoOption.logo_y, 10)
            self.media_player.video_set_logo_int(vlc.VideoLogoOption.logo_opacity, 150)
            self.media_player.video_set_logo_int(vlc.VideoLogoOption.logo_position, 6)
            self.media_player.video_set_logo_int(vlc.VideoLogoOption.logo_repeat, -1)

    def add_to_playlist(self, mrl):
        '''
        Adds a file to the playlist.

        Parameters:
            file_path (str): Path to the file.

        Returns:
            None   
        '''
        media = self.instance.media_new(mrl)
        self.list.add_media(media)
        logging.info('File added to play list: %s', mrl)

    def remove_from_playlist_by_mrl(self, mrl):
        '''
        Removes a file from the playlist. It searches the given path in the playlist and removes it.

        Parameters:
            file_path (str): Path to the file which shall be removed.

        Returns:
            None   
        '''
        logging.info('Searching for file %s in play list.', mrl)
        for i in range(self.list.count()):
            media = self.list.item_at_index(i)
            logging.info('Next file: %s', media.get_mrl())
            
            if media.get_mrl() == mrl:
                self.list.remove_index(i)
                logging.info('File removed from play list: %s', mrl)
                break
        else:
            logging.warning('Could not remove file from play list: %s. File not found.', mrl)

    def remove_from_playlist(self, index):
        '''
        Removes a file from the playlist. It removes the file with the given index.

        Parameters:
            index (int): Index of the file in the playlist which shall be removed.

        Returns:
            None   
        '''
        if 0 <= index < self.list.count():
            self.list.remove_index(index)
            logging.info('File removed from play list with index %s', index)

    def play_playlist(self, window_id):
        '''
        Plays the playlist.

        Parameters:
            window_id (int): Window ID in which the player shall be executed.

        Returns:
            None   
        '''
        # set the window id where to render VLC's video output
        if _isWindows:
            self.media_player.set_hwnd(window_id)
        else:
            self.media_player.set_xwindow(window_id)  # fails on Windows
        self.list_player.play()
        logging.info('Player started.')

    def stop_playlist(self):
        '''
        Stops the playlist.

        Parameters:
            None

        Returns:
            None   
        '''
        self.media_player.stop()
        logging.info('Player stoped.')

    def get_playlist(self):
        playlist = []
        for index in range(self.list.count()):
            playlist.append(self.list.item_at_index(index).get_mrl())
        return playlist

    def get_mrl(self, file_path):
        return self.instance.media_new(file_path).get_mrl()
        
    def is_playing(self):
        return self.media_player.is_playing()

    def will_play(self):
        return self.media_player.will_play()

class FolderHandler(object):
    '''
    This class observes the media folder. If a new file is added to this folder, this class adds
    the file to the playlist. If a file is removed, the class also removes it from the playlist.
    
    Args:
        None
    Attributes:
        None
    '''

    def __init__(self):
        self.sync_thread = None
        self.mount_path = MOUTN_PATH
        self.local_file_path = LOCAL_FILE_PATH
        self.allowed_extensions = ALLOWED_EXTENSIONS
        self.window_id = None

        self.playlist_manager = VLCPlaylistManager()

        # synchronize mounted files into local file path
        self._sync_local_files()
        self._sync_play_list()

    def start(self, window_id):
        '''
        Starts the observation of the media folder and starts the player.

        Parameters:
            window_id (int): Window ID in which the player shall be executed.

        Returns:
            None   
        '''
        self.sync_thread = threading.Thread(target=self.synchronize_thread)
        self.sync_thread.daemon = True
        self.sync_thread.start()
        self.window_id = window_id
        self.playlist_manager.play_playlist(window_id=self.window_id)

    def stop(self):
        '''
        Stops the observation of the media folder and stops the player.

        Parameters:
            window_id (int): Window ID in which the player shall be executed.

        Returns:
            None   
        '''
        self.playlist_manager.stop_playlist()

    def _has_allowed_extension(self, mrl):
        '''
        Checks if the file extension is supported. If not, the file will be ignored.

        Parameters:
            mrl (str): Mrl of the file.

        Returns:
            None   
        '''
        _, extension = os.path.splitext(mrl)
        return extension.lower() in self.allowed_extensions

    def _get_all_media_files(self):
        '''
        Gets all files in the observed folder.

        Parameters:
            None

        Returns:
            files (list of mrl)   
        '''
        files = []
        for f in os.listdir(self.local_file_path):
            file = os.path.join(self.local_file_path, f)
            if os.path.isfile(file) and self._has_allowed_extension(file):
                files.append(self.playlist_manager.get_mrl(file))
        return files

    def synchronize_thread(self):
        while True:
            try:
                logging.info("Started synchronization.")
                self._sync_local_files()
                self._sync_play_list()
                logging.info("Synchronization successful")
                logging.info("Player is playing: %s", self.playlist_manager.is_playing())
                logging.info("Player is able to play: %s", self.playlist_manager.will_play())
            except:
                logging.exception("Failed to synchronize data.")
            time.sleep(60)


    def _sync_local_files(self):
        '''
        Synchornizes destination folder into target folder.

        Parameters:
            None

        Returns:
            None
        '''
        logging.info('Synchronizing folder. Destination: %s, Target %s.', self.mount_path, self.local_file_path)
        sync(self.mount_path, self.local_file_path, 'sync', purge=True)
        self.list_of_files = self._get_all_media_files()

    def _sync_play_list(self):
        logging.info('Synchronizing play list.')
        playlist = self.playlist_manager.get_playlist()

        # remove deleted files from playlist
        for mrl in playlist:
            if (mrl in self.list_of_files):
                # file found, nothing to do
                pass
            else:
                # file not found. Delete it from playlist
                self.playlist_manager.remove_from_playlist_by_mrl(mrl)

        # add new files to playlist
        for mrl in self.list_of_files:
            found = False
            if (mrl in playlist):
                # mrl found, nothing to do any more
                found = True
                break
            else:
                # mrl not found. Go on searching.
                print("not found")
            
            if (not found):
                self.playlist_manager.add_to_playlist(mrl)
        
        playlist = self.playlist_manager.get_playlist()
        count_playlist = len(playlist)
        if (count_playlist == 0):
            logging.warning("No tracks in playlist")
        elif (count_playlist >= 1 and not self.playlist_manager.is_playing() and self.window_id):
            logging.info("Restart player.")
            self.playlist_manager.play_playlist(window_id=self.window_id)
                


class MainWindow(Tk.Frame):
    '''
    Main class which handles the window.
    
    Args:
        None
    Attributes:
        parent (Tk): Root window.
        title (str): title of the window
    '''
    def __init__(self, parent, title=None):
        self.logo_path = "C:/Users/marce/git/vlc-automated-player/watermark/Logo_Sporti.png"


        Tk.Frame.__init__(self, parent)
        self.parent = parent  # == root
        #self.parent.title(title or "VLC Automated Player")
        self.parent.attributes("-fullscreen", True)
        self.parent.bind("<Escape>", lambda x: self.parent.destroy())

        # top panel shows video
        self.canvas = Tk.Canvas(self.parent)
        self.canvas.pack(fill=Tk.BOTH, expand=1)

        # # Load watermark
        # self.logo_image = Image.open(self.logo_path)
        # self.logo_tk = ImageTk.PhotoImage(self.logo_image)
        # self.logo_image_id = self.canvas.create_image(0, 0, anchor="nw", image=self.logo_tk)

        # # Funktion zum Aktualisieren der Logo-Position in einem Intervall hinzufügen
        # self.canvas.after(10, self.update_logo_position)

        self.parent.update()

    def get_canvas_id(self):
        return self.canvas.winfo_id()


if __name__ == "__main__":

    # initialize logging
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    LOG_FILE_PATTH = "log/"
    LOG_FILE = "app.log"

    if not os.path.exists(LOG_FILE_PATTH):
        # create folder if it does not exist
        os.makedirs(LOG_FILE_PATTH)

    file_handler = RotatingFileHandler(LOG_FILE_PATTH + LOG_FILE, mode='a', maxBytes=5242880, backupCount=4, encoding=None, delay=False, errors=None)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s [%(module)s.%(funcName)s:%(lineno)d] %(message)s'))

    logger.addHandler(file_handler)

    logging.info('---------------------- Application started ----------------------')

    # read config
    config = configparser.ConfigParser()
    config.sections()
    config.read('config.ini')
    
    MOUTN_PATH = config["settings"]["mount_path"]
    LOCAL_FILE_PATH = config["settings"]["local_file_path"]
    ALLOWED_EXTENSIONS = config["settings"]["allowed_extensions"].split(',')
    ALLOWED_EXTENSIONS = ['.' + extension for extension in ALLOWED_EXTENSIONS]
    WATERMARK_FILE = config["settings"]["watermark_file"]

    logging.info('Path to videos: %s', LOCAL_FILE_PATH)
    
    # create window
    root = Tk.Tk()
    
    # initialize main window
    window = MainWindow(parent=root)

    # initialize FolderHandler
    folder_handler = FolderHandler()

    folder_handler.start(window.get_canvas_id())

    # run main loop
    root.mainloop()
    
    # if user closes the window, stop the player
    folder_handler.stop()
