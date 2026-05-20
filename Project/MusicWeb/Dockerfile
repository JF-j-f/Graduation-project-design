FROM maven:3.9.9-eclipse-temurin-23

WORKDIR /app/Project/MusicWeb

COPY pom.xml ./
COPY src ./src

RUN mvn -DskipTests package

EXPOSE 8082

CMD ["mvn", "-DskipTests", "cargo:run"]
