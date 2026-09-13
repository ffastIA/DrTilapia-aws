FROM node:18-alpine
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci --only=production
COPY frontend/ .
EXPOSE 3000
CMD ["npm", "run", "start"]