#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2015 Dawid Sawa
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation;
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

import multiprocessing
import queue
import requests
import sys
import threading
from PIL import Image
from io import StringIO

class DownloadThread(threading.Thread):
    def __init__(self, tile_info_queue, tile_queue):
        threading.Thread.__init__(self)
        self.tile_info_queue = tile_info_queue
        self.tile_queue = tile_queue

    def run(self):
        while True:
            tile_url, tile_size, tile_column, tile_row = self.tile_info_queue.get()
            response = requests.get(tile_url)
            response.raise_for_status()
            tile = Image.open(StringIO(response.content))
            tile_x = tile_column * tile_size
            tile_y = tile_row * tile_size
            self.tile_queue.put((tile, tile_x, tile_y))
            self.tile_info_queue.task_done()

class MergeThread(threading.Thread):
    def __init__(self, tile_queue, image):
        threading.Thread.__init__(self)
        self.tile_queue = tile_queue
        self.image = image

    def run(self):
        while True:
            tile, tile_x, tile_y = self.tile_queue.get()
            self.image.paste(tile, (tile_x, tile_y))
            self.tile_queue.task_done()

def spawn_thread_pool(thread, size, *args):
    for _ in range(size):
        job = thread(*args)
        job.setDaemon(True)
        job.start()

def get_grid_size(image_id):
    response = requests.get('http://api.zoomhub.net/v1/content/' + image_id)
    response.raise_for_status()
    dzi = response.json()['dzi']
    width = dzi['width']
    height = dzi['height']
    tile_size = dzi['tileSize']
    return (width, height, tile_size, width / tile_size + 1, height / tile_size + 1)

def populate_tile_info_queue(queue, image_id, tile_size, columns, rows):
    for x in range(columns):
        for y in range(rows):
            url = 'http://content.zoomhub.net/dzis/%s_files/13/%d_%d.jpg' % (image_id, x, y)
            queue.put((url, tile_size, x, y))

def download_image(image_id):
    jobs = multiprocessing.cpu_count()
    width, height, tile_size, columns, rows = get_grid_size(image_id)

    tile_info_queue = Queue.Queue()
    tile_queue = Queue.Queue()

    spawn_thread_pool(DownloadThread, jobs, tile_info_queue, tile_queue)
    populate_tile_info_queue(tile_info_queue, image_id, tile_size, columns, rows)
    image = Image.new('RGB', (width, height))
    spawn_thread_pool(MergeThread, jobs, tile_queue, image)

    tile_info_queue.join()
    tile_queue.join()
    image.save(image_id + '.jpg')

def main():
    for image_id in sys.argv[1:]:
        download_image(image_id)

if __name__ == '__main__':
    main()
