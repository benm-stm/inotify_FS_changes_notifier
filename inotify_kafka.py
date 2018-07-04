#!/usr/bin/env python

import os
import copy
from inotify_simple import INotify, flags
import threading, logging, time
from kafka import KafkaProducer
import json
import re
import uuid

class Watcher():
    def __init__(self, watched_dir, watch_flags, web_server_url, kafka_url, kafka_topic_name):
        self.watched_name = {}
        self.watched_dir = watched_dir
        self.watch_flags = watch_flags
        self.web_server_url = web_server_url
        self.kafka_url = kafka_url
        self.kafka_topic_name = kafka_topic_name
        #init inotify
        self.init_inotify()

    def init_inotify(self):
        self.inotify = INotify()
        self.dirs_array = self.discover_tree(self.watched_dir)
        for dir in self.dirs_array:
           self.watched_name[self.inotify.add_watch(dir, self.watch_flags)] = dir
        print(str(self.watched_name))

    def discover_tree(self, dir_path):
        dirs_array = []
        for dirpath, dirs, files in os.walk(dir_path):
            dirs_array.append(dirpath)
        return dirs_array

    def inotify_watch(self):
        for event in self.inotify.read():
            print(event.name)
            flags_concat = ''
            for flag in flags.from_mask(event.mask):
                self.update_watch_list(flags, event)
                print('    ' + str(flag))
                #get the nature of the event
                flags_concat = flags_concat + str(flag)
            #if not re.search(".*flags.ISDIR", flags_concat):
            json_data = self.json_formatter_to_kafka(event, flags_concat)
            print(str(json_data))
                #Kafka_producer(self.kafka_url, self.kafka_topic_name).run(json_data)
        self.inotify_watch()

    def json_formatter_to_kafka(self, event, flags_concat):
        attributes = {}
        attributes['title'] = event.name
        #import pdb; pdb.set_trace()
        attributes['path'] = self.watched_name[event.wd] + '/' + event.name
        attributes['owner_id'] = uuid.uuid4().hex

        data = {}
        attributes['type'] = 'file'
        if re.search(".*flags.ISDIR", flags_concat):
            attributes['type'] = 'folder'
            flags_concat = flags_concat.replace('flags.', '').replace('ISDIR', '')
        data['operation'] = flags_concat
        data['id'] = uuid.uuid4().hex
        data['attributes'] = attributes
                
        msg = {}
        msg['link'] = self.web_server_url + '/' + self.watched_name[event.wd].split('/', 1)[-1] + '/' + event.name
        msg['data'] = data
                
        return json.dumps(msg)

    def have_sub_dir(self, dir):
        dirs_array = []
        for dirpath, dirs, files in os.walk(dir):
            dirs_array.append(dirpath)
        if len(dirs_array) > 1 :
            return True
        return False

    def update_watch_list(self, flags, event):
        flags_concat = ''
        #used to add or remove a watch on a folder
        for flag in flags.from_mask(event.mask):
            flags_concat = flags_concat + str(flag)

        if flags_concat == "flags.CREATEflags.ISDIR":
            self.create_watch_list(flags, event)
        #this sectio is used to remove the entry from the watch dictionary
        elif (flags_concat == "flags.DELETEflags.ISDIR") or (flags_concat == "flags.DELETE_SELF"):
            self.delete_watch_list(flags, event)

    def delete_watch_list(self, flags, event):
        print(str(event))
        print(str(self.watched_name))
        if event.wd in self.watched_name:
            folder_to_remove_path = self.watched_name[event.wd]
            #tmp var because of dictionary changed size error
            tmp_watched_name =  copy.deepcopy(self.watched_name)
            for wd, path in tmp_watched_name.iteritems():
                if re.search("^(%s).*"%folder_to_remove_path, tmp_watched_name[wd]):
                    del self.watched_name[wd]
        '''here we have an issue the inotify lib does not list all removed folders when we rm recursively !!!!! 
           same thing is applied for files!
           a clamsy solution is to stop the watch and reinitialyze it bad but should work'''

    def create_watch_list(self, flags, event):
        new_folder_path = self.watched_name[event.wd] + '/' + event.name
        #if there are sub dirs, i'll iterate and watch them
        if self.have_sub_dir(new_folder_path):
            dirs_array =  self.discover_tree(new_folder_path)
            for dir in dirs_array:
                self.watched_name[self.inotify.add_watch(dir, self.watch_flags)] = dir
        #if no sub dirs only watch the newly created one
        else:
            self.watched_name[self.inotify.add_watch(new_folder_path, self.watch_flags)] = new_folder_path
        print(str(self.watched_name))

class Kafka_producer(threading.Thread):
    def __init__(self, kafka_url, kafka_topic_name):
        self.kafka_url = kafka_url
        self.kafka_topic_name = kafka_topic_name
        threading.Thread.__init__(self)
        self.stop_event = threading.Event()
        
    def stop(self):
        self.stop_event.set()

    def run(self, json_data):
        #import pdb; pdb.set_trace()  
        producer = KafkaProducer(bootstrap_servers=self.kafka_url)

        while not self.stop_event.is_set():
            producer.send(self.kafka_topic_name, json_data)
            time.sleep(1)

        producer.close()

def main():
    #params
    watched_dir = os.getenv('WATCHED_ROOT_DIR', '/watched_dir')
    watch_flags = flags.CREATE | flags.DELETE | flags.DELETE_SELF | flags.MOVED_FROM | flags.MOVED_TO
    webserver_url = os.getenv('WEBSERVER_URL', '127.0.0.1:9000')
    kafka_url = os.getenv('KAFKA_URL', 'kafka:9092')
    kafka_topic_name = os.getenv('KAFKA_TOPIC', 'topic')

    #begin the watch
    Watcher(watched_dir, watch_flags, webserver_url, kafka_url, kafka_topic_name).inotify_watch()
        
if __name__ == "__main__":
    logging.basicConfig(
        format='%(asctime)s.%(msecs)s:%(name)s:%(thread)d:%(levelname)s:%(process)d:%(message)s',
        level=logging.INFO
        )
    main()
