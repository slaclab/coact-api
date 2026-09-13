FROM node:alpine

# RUN apk add --no-cache bash curl

WORKDIR /app
COPY . /app

RUN npm install react-scripts \
  && npm install  \
  && npm run build \
  && npm install -g serve

ENTRYPOINT [ "serve", "-s", "build" ]
