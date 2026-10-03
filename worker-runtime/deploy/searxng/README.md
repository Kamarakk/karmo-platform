# SearXNG for KARMO web search (Worker02)

The worker's `web_search` capability calls `http://127.0.0.1:8888/search?format=json`.
SearXNG runs in a container bound to loopback only. It is the only part that reaches
the search engines; nothing is fetched from result pages.

Install, on Worker02:

```
sudo install -d -m 755 /etc/karmo/searxng
sudo cp settings.yml /etc/karmo/searxng/settings.yml
sudo sed -i "s/__SECRET_KEY__/$(openssl rand -hex 32)/" /etc/karmo/searxng/settings.yml
sudo docker run -d --name karmo-searxng --restart unless-stopped \
  -p 127.0.0.1:8888:8080 -v /etc/karmo/searxng:/etc/searxng \
  --cap-drop ALL --cap-add CHOWN --cap-add SETGID --cap-add SETUID \
  docker.io/searxng/searxng:latest
curl -s 'http://127.0.0.1:8888/search?q=begonia&format=json' | head -c 300
```

Undo: `sudo docker rm -f karmo-searxng`.
