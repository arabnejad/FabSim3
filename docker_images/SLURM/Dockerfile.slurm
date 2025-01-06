# Use the base image
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ENTRYPOINT ["sh", "-c", "service ssh start && /entrypoint.sh"]