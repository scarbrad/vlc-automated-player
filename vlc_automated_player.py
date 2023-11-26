
import configparser

import logging
from logging.handlers import RotatingFileHandler

import os
import sys

import tkinter as Tk
from tkinter import ttk

import vlc

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


_isWindows = sys.platform.startswith('win')
_isLinux   = sys.platform.startswith('linux')



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
        args = []
        if _isLinux:
            args.append('--no-xlib')
        self.instance = vlc.Instance(args)
        self.player = self.instance.media_player_new()
        self.list_player = self.instance.media_list_player_new()
        self.list = self.instance.media_list_new()
        self.list_player.set_media_list(self.list)
        self.list_player.set_media_player(self.player)

    def add_to_playlist(self, file_path):
        '''
        Adds a file to the playlist.

        Parameters:
            file_path (str): Path to the file.

        Returns:
            None   
        '''
        media = self.instance.media_new(file_path)
        self.list.add_media(media)
        logging.info('File added to play list: %s', file_path)

    def remove_from_playlist_by_filename(self, file_path):
        '''
        Removes a file from the playlist. It searches the given path in the playlist and removes it.

        Parameters:
            file_path (str): Path to the file which shall be removed.

        Returns:
            None   
        '''
        logging.info('Searching for file %s in play list.', file_path)
        for i in range(self.list.count()):
            media = self.list.item_at_index(i)
            logging.info('Next file: %s', media.get_mrl())
            print(media.get_mrl())
            if os.name == 'nt': # for Windows
                file_prefix = 'file:///'
            else: # for Linux (and others?)
                file_prefix = 'file://'
            if media.get_mrl() == file_prefix + file_path:
                self.list.remove_index(i)
                logging.info('File removed from play list: %s', file_path)
                break
        else:
            logging.warning('Could not remove file from play list: %s. File not found.', file_path)

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
            self.player.set_hwnd(window_id)
        else:
            self.player.set_xwindow(window_id)  # fails on Windows
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
        self.player.stop()
        logging.info('Player stoped.')


class FolderHandler(FileSystemEventHandler):
    '''
    This class observes the media folder. If a new file is added to this folder, this class adds
    the file to the playlist. If a file is removed, the class also removes it from the playlist.
    
    Args:
        None
    Attributes:
        folder_to_watch (str): Path to the media folder which is observed.
    '''

    ALLOWED_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.wmv', '.mov'}

    def __init__(self, folder_to_watch):
        self.folder_to_watch = folder_to_watch

        self.observer = Observer()
        self.observer.schedule(self, self.folder_to_watch, recursive=True)

        self.list_of_files = self._get_all_files()

        self.playlist_manager = VLCPlaylistManager()
        for file in self.list_of_files:
            self._add_to_playlist(self.folder_to_watch + file)

    def start(self, window_id):
        '''
        Starts the observation of the media folder and starts the player.

        Parameters:
            window_id (int): Window ID in which the player shall be executed.

        Returns:
            None   
        '''
        self.observer.start()
        self.playlist_manager.play_playlist(window_id=window_id)

    def stop(self):
        '''
        Stops the observation of the media folder and stops the player.

        Parameters:
            window_id (int): Window ID in which the player shall be executed.

        Returns:
            None   
        '''
        self.observer.stop()
        self.playlist_manager.stop_playlist()

    def on_created(self, event):
        '''
        Event is executed when a new file was crated in the observed folder.

        Parameters:
            event (str): Path to the new file.

        Returns:
            None   
        '''
        if event.is_directory:
            logging.info('Folder was created: %s.', event.src_path)
        else:
            self._add_to_playlist(event.src_path)

    def on_deleted(self, event):
        '''
        Event is executed when a file was deleted from the observed folder.

        Parameters:
            event (str): Path to the deleted file.

        Returns:
            None   
        '''
        if event.is_directory:
            logging.info('Folder was removed: %s.', event.src_path)
        else:
            self.playlist_manager.remove_from_playlist_by_filename(event.src_path)

    def _add_to_playlist(self, file_path):
        '''
        Adds a file to the playlist.

        Parameters:
            file_path (str): Path to the file.

        Returns:
            None   
        '''
        if self._is_allowed_extension(file_path):
            self.playlist_manager.add_to_playlist(file_path)
        else:
            logging.warning('File does not have a supported file extension: %s. Ignoring it.', file_path)

    def _is_allowed_extension(self, file_path):
        '''
        Checks if the file extension is supported. If not, the file will be ignored.

        Parameters:
            file_path (str): Path to the file.

        Returns:
            None   
        '''
        _, extension = os.path.splitext(file_path)
        return extension.lower() in self.ALLOWED_EXTENSIONS

    def _get_all_files(self):
        '''
        Gets all files in the observed folder.

        Parameters:
            None

        Returns:
            files (list of str)   
        '''
        files = [f for f in os.listdir(self.folder_to_watch) if os.path.isfile(os.path.join(self.folder_to_watch, f))]
        return files


class Player(Tk.Frame):
    '''
    Main class which handles the window.
    
    Args:
        None
    Attributes:
        parent (Tk): Root window.
        folder_to_watch (str): folder which shall be observed.
        title (str): title of the window
    '''
    def __init__(self, parent, folder_to_watch, title=None):
        Tk.Frame.__init__(self, parent)

        self.parent = parent  # == root
        self.parent.title(title or "Automated Player")

        # first, top panel shows video
        self.videopanel = ttk.Frame(self.parent)
        self.canvas = Tk.Canvas(self.videopanel)
        self.canvas.pack(fill=Tk.BOTH, expand=1)
        self.videopanel.pack(fill=Tk.BOTH, expand=1)

        
        # initialize folder handler
        self.folder_handler = FolderHandler(folder_to_watch)

        self.parent.update()


    def start(self):
        '''
        Starts the observer and the playlist.

        Parameters:
            None

        Returns:
            None
        '''
        self.folder_handler.start(self.videopanel.winfo_id())

    def stop(self):
        '''
        Stops the observer and the playlist.

        Parameters:
            None

        Returns:
            None
        '''
        self.folder_handler.stop()


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

    logging.info('---------------------- Application started ----------------------')

    # read config
    config = configparser.ConfigParser()
    config.sections()
    config.read('config.ini')

    folder_to_watch = config["settings"]["file_path"]
    logging.info('Path to videos: %s', folder_to_watch)


    # create window
    root = Tk.Tk()
    root.attributes("-fullscreen", True)
    root.bind("<Escape>", lambda x: root.destroy())
    
    # initialize and start player
    player = Player(parent=root, folder_to_watch=folder_to_watch)
    player.start()

    # run main loop
    root.mainloop()
    
    # if user closes the window, stop the player
    player.stop()
