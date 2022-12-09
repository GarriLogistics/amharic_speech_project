import firebase_admin
import urllib
import json
import pytube
import os
import zipfile 
import shutil
import time 
from ffmpy import FFmpeg, FFprobe
from urllib.request import urlopen
from google.cloud import storage
from firebase_admin import db

# How much space to leave free on the drive before zipping, uploading, and deleting
MAX_FREE = 100000000000#105072455680 * 0.4

def download_video_from_yt(link, dest):
    yt = pytube.YouTube(link)
    try:
        print(yt.title)
    except Exception:
        exit(0)

    if os.path.exists(os.path.join(dest, '{}.mp4'.format(yt.title))):
        print('PASS VIDEO ALREADY DL {}'.format(yt.title))
        return os.path.join(dest, '{}.mp4'.format(yt.title))
    desStream = None

    for i in yt.streams.filter(only_audio=True).all():  # (file_extension='mp4').all():
        if i.mime_type == 'audio/mp4' and i.abr == '128kbps':
            desStream = i
    if desStream == None:
        desStream = yt.streams.filter(only_audio=True).order_by('mime_type').desc().first()
    print('Attempt to download')


    filepath_to_return = os.path.join(dest, yt.title.replace('/', '') + '.mp4')
    filename_to_download = yt.title.replace('/', '') + '.mp4'


    if len(filepath_to_return) > 120:
        filename_to_download = 'temp_too_long_{}'.format(time.time()).replace('.', '-') + '.mp4'
        filepath_to_return = os.path.join(dest, filename_to_download)
    

    desStream.download(dest, filename=filename_to_download)
    print('Downloaded ', yt.title)
    return filepath_to_return, yt.title

def zipdir(path, ziph):
    # ziph is zipfile handle
    for root, dirs, files in os.walk(path):
        for file in files:
            print('zipping up {}'.format(file))
            ziph.write(os.path.join(root, file), 
                       os.path.relpath(os.path.join(root, file), 
                                       os.path.join(path, '..')))

def zip_and_upload(dir_target, zip_path, zip_index, json_for_upload, channel_tag):
    json_target = os.path.join(dir_target, 'json.json')
    with open(json_target, 'w') as f:
        json.dump(json_for_upload, f)


    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipdir(dir_target, zipf)


    db.reference('audiodata/{}'.format(channel_tag)).push(json_for_upload)
    storage_client = storage.Client.from_service_account_json('/temp/service/acc.sjon')
    bucket = storage_client.get_bucket('sample_bucket')
    blob = bucket.blob('audiodata/{}/zip_{}.zip'.format(channel_tag, zip_index))
    blob.upload_from_filename(zip_path)

    shutil.rmtree(dir_target)
    print('zipped {}'.format(zip_path))

    os.remove(zip_path)
    print('Uploaded zip_{}'.format(zip_index))

def get_all_video_in_channel(channel_id):
    api_key = 'YOUTUBE_API_KEY'

    base_video_url = 'https://www.youtube.com/watch?v='
    base_search_url = 'https://www.googleapis.com/youtube/v3/search?'

    first_url = base_search_url+'key={}&channelId={}&part=snippet,id&order=date&maxResults=25'.format(api_key, channel_id)

    video_links = []
    url = first_url

    file_index = 0
    zip_index = 0
    json_for_index = {}

    topdir = os.path.join('/mnt/disks/MOUNT_DIR')
    
    basedir = os.path.join(topdir, '{}'.format(file_index))
    
    if os.path.exists(basedir):
        shutil.rmtree(basedir)
    
    if not os.path.exists(basedir):
        os.mkdir(basedir)
    

    while True:
        inp = urlopen(url)
        resp = json.load(inp)

        for i in resp['items']:
            if i['id']['kind'] == "youtube#video":

                channel_title = i['snippet']['channelTitle']
                channel_id = i['snippet']['channelId']
                channel_tag = '{}-ID-{}-{}'.format(channel_title, channel_id, time.time()).replace('.', '-')

                video_id = i['id']['videoId']

                # TODO: Instead of hardcoding streaming videos, add method to check for streaming
                lsblock = {'s5Yd0be0u3I': 1, '1TPP7UY40Sk': 1, '0BeYwsQC2OU': 1, 'Xmz4_a8zCek': 1}

                if video_id in lsblock:
                    print('skip for streaming live {}'.format(video_id)))
                    continue

                video_link = 'https://www.youtube.com/watch?v={}'.format(video_id)

                dest = None 
                title = None

                try:
                    dest, title = download_video_from_yt(video_link, basedir)
                except Exception as e:
                    print('error')
                    print(e)
                    continue

                # if the video is shorter than 5 minutes, just delete it and do nothing else
                duration = get_length(dest)
                if duration < 300:
                    os.remove(dest)
                    continue
                
                json_for_index[file_index] = {'duration': duration, 'trimmed_duration': duration - 30, 'video_id': video_id, 'name': os.path.basename(dest), 'title': title}
                file_index += 1
                # clip path is the same video with "clip" appended just before the extension
                clip_path = dest[:-4] + 'clip' + dest[-4:]
                
                clip_wav(dest, clip_path)
                os.remove(dest)

                t,u,f = shutil.disk_usage(topdir)
                if f < MAX_FREE:

                    zip_and_upload(basedir, os.path.join(topdir, 'zip_{}.zip'.format(zip_index)), zip_index, json_for_index, channel_tag)
                    zip_index += 1
                    file_index = 0
                    json_for_index = {}
                    basedir = os.path.join(topdir, '{}'.format(zip_index))
                
                    if os.path.exists(basedir):
                        shutil.rmtree(basedir)
                    
                    if not os.path.exists(basedir):
                        os.mkdir(basedir)
                    #print('Not enough space to convert to wav')
                    #continue

                # instead of wav we should convert them to flac? They take too much space as mp3 or wav
                if False:
                    dest_as_wav = dest.replace('mp4', 'wav')
                    convert_mp4_to_wav(dest, dest_as_wav)

        try:
            next_page_token = resp['nextPageToken']
            url = first_url + '&pageToken={}'.format(next_page_token)
        except:
            break
    if file_index > 0:
        zip_and_upload(basedir, os.path.join(topdir, 'zip_{}.zip'.format(zip_index)), zip_index, json_for_index, channel_tag)


def convert_mp4_to_wav(input_path_unquote, output_path_unqoute):

    # add quotes to input and output path in case of spaces in the names
    input_path = '"' + input_path_unquote + '"'
    output_path = '"' + output_path_unqoute + '"'

    ffmpeg_inputs = {input_path: None}
    command_string = ''

    ffmpeg = FFmpeg(
        executable=fmp,
        inputs=ffmpeg_inputs,
        outputs={output_path: command_string}
    )

    print(ffmpeg.cmd)
    ffmpeg.run()

def clip_wav(input_path, output_path):
    ffmpeg_inputs = {input_path: '-y -ss 40'}
    command_string = '-c copy'#'-t 30'

    ffmpeg = FFmpeg(
        inputs=ffmpeg_inputs,
        outputs={output_path: command_string}
    )

    print(ffmpeg.cmd)
    ffmpeg.run()

def get_length(vid):
    outputVideoFile = vid
    test = FFprobe(
    #executable='/usr/local/bin/ffprobe',  # adapt this according to your environment
    inputs={outputVideoFile: '-v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1'})
    
    # Need to write to a file because the output might have characters not supported for stdout
    with open('duartion_tmp.txt', 'w') as output_file:
        test.run(stdout=output_file)

    # open and red the file 
    with open('duration_tmp.txt', 'r') as f:
        # read the file and convert the string to float
        duration = float(f.read())
    return duration





channel_ids = ['UCkWMRjNOKr3U8glg5WhY_6A', 
    , 'UCSYM-vgRrMYsZbG-Z7Kz0Pw'
    , 'UCOhrz3uRCOHmK6ueUstw7_Q'
    , 'UCmRUjfsKUB5PDyllhGD1V3Q'
    , 'UCyuuWxAHVMZp_WQ7yEEUjcg'
    , 'UCc9hwVZQkG5XP8Km9zFRmxg'
    , 'UCYMNGgMWNecwrrvVMKcEhKg'
    , 'UCESu04KeFNgxeQOPHk96Ixw'
    , 'UCbe-CGWs9wSa0M01_J9gctg'
    , 'UCpl1tIuSEIA_0lx_6KUqaIg'
    , 'UC-pKko5K441OJeYE9gZUo9Q'
    , 'UC-Ontcokih_EvGGW4hyGQIw'
    , 'UCVcc_sbg3AcXLV9vVufJrGg'
    , 'UCZtXd8pSeqURf5MT2fqE51g'
    , 'UChOj6gMUyJkBarUc7eNrKfA'
    , 'UCgT0spJhHiDbDW2Opq0X6fQ'
    , 'UChhz3MNezNfy_M05TUDTEQA'
    , 'UC0LjMR-ZJ2lUBt17zVNHfZw'
    , 'UCheNCov-o0DLrWCVTm0Wqaw'
    , 'UCkOxp2i-ltA9jj0uSamcFWQ'
    , 'UCTIsElX_myTJUJwQpsdveNQ'
    , 'UCSp3GYteSRXZ49u44zzKkGA'
    , 'UCsF7ipqw0jj7HO99BFBZkpg'
    , 'UCONY-Fi6-aODgdOdmcesDqg'
    , 'UCdQ-5b2xJiCWgxinWo4NX7w']

for channel_id in channel_ids:
    get_all_video_in_channel(channel_id)
