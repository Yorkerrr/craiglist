# Kyzya

Crawl craiglist

## build
docker build -t craig .
## run
docker run -t -i -e CHAT_ID='$__CHAT_ID__' -e TOKEN='$__API__' -e BOT_URL='$__BOT_URL__' craig
