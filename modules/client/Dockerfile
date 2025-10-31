# Use an official Node.js runtime as the parent image
FROM node:24

# Install dumb-init for proper signal handling
RUN apt-get update && apt-get install -y dumb-init

# Set the working directory in the Docker container to /app
WORKDIR /app

# Copy package.json and package-lock.json to the Docker container
COPY package*.json ./

# Install the dependencies in the Docker container
RUN npm install

# Copy the rest of your application's source files to the Docker container
COPY . .

# Build the application
RUN npm run build

# Make port 3001 available in development and production
EXPOSE 3001

# Use dumb-init to run your process
ENTRYPOINT ["dumb-init", "--"]

# Define the command to run the app
CMD ["npm", "start"]