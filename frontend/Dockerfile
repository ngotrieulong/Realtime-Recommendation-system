# Build stage
FROM node:18-alpine

WORKDIR /app

# Install dependencies
COPY package.json ./
RUN npm install

# Copy source code
COPY . .

# Expose port
EXPOSE 3000

# Start command (development mode for now to support volumes if needed)
CMD ["npm", "start"]
