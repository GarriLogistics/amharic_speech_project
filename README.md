# Amharic Speech Recognition
We are working to develop and open source dataset and Speech Recognition model to accurately transcribe Amharic audio.


# Data Scraper

This is a simple scraper to grab audio from youtube videos based on Channel ID. The IDs in the list include channels we've scraped, including news, sports, podcasts etc.
For each video on a channel, it will download, remove the video element, and save the file. If the disk is getting too full it will compress the files and upload them before deleting the local copies and moving on.

You'll need ffmpeg installed
` sudo apt install ffmpeg `

So far we have used GCP Buckets and Firebase to store audio files and metadata, respectively. Feel free to replace with your own temporary storage solution if you play with the script.
