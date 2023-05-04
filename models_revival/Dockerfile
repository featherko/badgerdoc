FROM python:3.8.10-buster AS base

RUN apt-get update \
    && apt-get install --yes build-essential \
       pkg-config cmake wget curl \
       software-properties-common libmagickwand-dev \
    && apt-get update \
    && add-apt-repository https://archive.ubuntu.com/ \
    && apt-get install -y ghostscript \
    && rm -rf /var/lib/apt/lists/* \

WORKDIR /model_api

COPY pyproject.toml .
RUN pip install poetry \
    && poetry config virtualenvs.create false \
    && poetry install --no-root --no-interaction

ENV imagemagic_config=/etc/ImageMagick-6/policy.xml
RUN if [ -f $imagemagic_config ] ; then sed -i 's/<policy domain="coder" rights="none" pattern="PDF" \/>/<policy domain="coder" rights="read|write" pattern="PDF" \/>/g' $imagemagic_config ; else echo did not see file $imagemagic_config ; fi

ENV PYTHONUNBUFFERED 1

COPY .. /model_api/
RUN poetry install --no-interaction

FROM base AS build
CMD ["python", "-m", "model_api"]