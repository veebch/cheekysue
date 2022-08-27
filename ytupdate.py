#!/usr/bin/python3
# A script to run as a cronjob every 10 minutes that adjusts the title (of our currently least popular video) based on how many comments it has
import os, pickle
import argparse

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import google.oauth2.credentials
import google_auth_oauthlib.flow
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
import urllib.parse as p
import re

def pickle_file_name(
        api_name = 'youtube',
        api_version = 'v3'):
    return f'token_{api_name}_{api_version}.pickle'

def load_credentials(
        api_name = 'youtube',
        api_version = 'v3'):
    pickle_file = pickle_file_name(
        api_name, api_version)

    if not os.path.exists(pickle_file):
        return None

    with open(pickle_file, 'rb') as token:
        return pickle.load(token)

def save_credentials(
        cred, api_name = 'youtube',
        api_version = 'v3'):
    pickle_file = pickle_file_name(
        api_name, api_version)

    with open(pickle_file, 'wb') as token:
        pickle.dump(cred, token)

def create_service(
        client_secret_file, scopes,
        api_name = 'youtube',
        api_version = 'v3'):
    print(client_secret_file, scopes,
        api_name, api_version,
        sep = ', ')

    cred = load_credentials(api_name, api_version)

    if not cred or not cred.valid:
        if cred and cred.expired and cred.refresh_token:
            cred.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                    client_secret_file, scopes)
            cred = flow.run_console()

    save_credentials(cred, api_name, api_version)
    
    try:
        service = build(api_name, api_version, credentials = cred)
        print(api_name, 'service created successfully')
        return service
    except Exception as e:
        print(api_name, 'service creation failed:', e)
        return None

def update_video(youtube, args):
  # Call the API's videos.list method to retrieve the video resource.
  videos_list_response = youtube.videos().list(
    id=args.video_id,
    part='snippet'
  ).execute()

  # If the response does not contain an array of 'items' then the video was
  # not found.
  if not videos_list_response['items']:
    print ('Video "%s" was not found.' % args.video_id)
    sys.exit(1)

  # Since the request specified a video ID, the response only contains one
  # video resource. This code extracts the snippet from that resource.
  videos_list_snippet = videos_list_response['items'][0]['snippet']

  # Set video title, description, default language if specified in args.
  if args.title:
    videos_list_snippet['title'] = args.title
  if args.description:
    videos_list_snippet['description'] = args.description

  # Preserve any tags already associated with the video. If the video does
  # not have any tags, create a new array. Append the provided tag to the
  # list of tags associated with the video.
  if 'tags' not in  videos_list_snippet:
    videos_list_snippet['tags'] = []
  if args.tags:
    videos_list_snippet['tags'] = args.tags.split(',')
  elif args.add_tag:
    videos_list_snippet['tags'].append(args.add_tag)

  print(videos_list_snippet);

  # Update the video resource by calling the videos.update() method.
  videos_update_response = youtube.videos().update(
    part='snippet',
    body=dict(
      snippet=videos_list_snippet,
      id=args.video_id
    )).execute()

  print('The updated video metadata is:\n' +
        'Title: ' + videos_update_response['snippet']['title'] + '\n')
  if videos_update_response['snippet']['description']:
    print ('Description: ' +
           videos_update_response['snippet']['description'] + '\n')
  if videos_update_response['snippet']['tags']:
    print ('Tags: ' + ','.join(videos_update_response['snippet']['tags']) + '\n')

def get_video_id_by_url(url):
    """
    Return the Video ID from the video `url`
    """
    # split URL parts
    parsed_url = p.urlparse(url)
    # get the video ID by parsing the query of the URL
    video_id = p.parse_qs(parsed_url.query).get("v")
    if video_id:
        return video_id[0]
    else:
        raise Exception(f"Wasn't able to parse video URL: {url}")

def get_video_details(youtube, **kwargs):
    return youtube.videos().list(
        part="snippet,contentDetails,statistics",
        **kwargs
    ).execute()

def print_video_infos(video_response):
    items = video_response.get("items")[0]
    # get the snippet, statistics & content details from the video response
    snippet         = items["snippet"]
    statistics      = items["statistics"]
    content_details = items["contentDetails"]
    # get infos from the snippet
    channel_title = snippet["channelTitle"]
    title         = snippet["title"]
    description   = snippet["description"]
    publish_time  = snippet["publishedAt"]
    # get stats infos
    comment_count = statistics["commentCount"]
    like_count    = statistics["likeCount"]
    view_count    = statistics["viewCount"]
    # get duration from content details
    duration = content_details["duration"]
    # duration in the form of something like 'PT5H50M15S'
    # parsing it to be something like '5:50:15'
    parsed_duration = re.search(f"PT(\d+H)?(\d+M)?(\d+S)", duration).groups()
    duration_str = ""
    for d in parsed_duration:
        if d:
            duration_str += f"{d[:-1]}:"
    duration_str = duration_str.strip(":")
    print(f"""\
    Title: {title}
    Description: {description}
    Channel Title: {channel_title}
    Publish time: {publish_time}
    Duration: {duration_str}
    Number of comments: {comment_count}
    Number of likes: {like_count}
    Number of views: {view_count}
    """)
    return title, comment_count


def main():
    os.chdir("/home/mart/sandbox/youtubey/")
    youtube = create_service("client_secret.json",
    ["https://www.googleapis.com/auth/youtube.force-ssl"])
    videoid="47cM1lvHEzI"
    titleroot="Hot Wire Cutting: This video has "
    video_url = "https://www.youtube.com/watch?v="+videoid+"&ab_channel=jawed"
    # parse video ID from URL
    video_id = get_video_id_by_url(video_url)
    # make API call to get video info
    response = get_video_details(youtube, id=video_id)
    # print extracted video infos
    title, comment_count = print_video_infos(response)
    # Check whether we need to change the title
    if title  == titleroot+str(comment_count)+" comments.":
        titlechange=False
    else:
        newtitle = titleroot+str(comment_count)+" comments."
        titlechange= True
    parser = argparse.ArgumentParser()
    parser.add_argument('--video_id', help='ID of video to update.',
    default=videoid)
    parser.add_argument('--tags',
        help='Comma-separated list of tags relevant to the video. This argument ' +
        'replaces the existing list of tags.')
    parser.add_argument('--add_tag', help='Additional tag to add to video. ' +
        'This argument does not affect current tags.')
    if titlechange==True:
        parser.add_argument('--title', help='Title of the video.',
        default=newtitle)
    else:
        parser.add_argument('--title', help='Title of the video.')
    parser.add_argument('--description', help='Description of the video.')
    args = parser.parse_args()
    if not youtube: return
    try:
        update_video(youtube, args)
    except HttpError as e:
        print ('An HTTP error %d occurred:\n%s' % (e.resp.status, e.content))
        print ('Tag "%s" was added to video id "%s".' % (args.add_tag, args.video_id))
if __name__ == '__main__':
    main()
