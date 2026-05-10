FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY index.html ./
COPY tsconfig.json tsconfig.node.json vite.config.ts ./
COPY src ./src
COPY tests ./tests

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
