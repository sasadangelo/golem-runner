FROM mcp/filesystem
RUN npm install -g supergateway
ENTRYPOINT ["supergateway", "--stdio", "node /app/dist/index.js /data", "--outputTransport", "streamableHttp", "--port", "8000"]
