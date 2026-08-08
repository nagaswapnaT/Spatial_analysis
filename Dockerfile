# Mirrors AWS Glue 5.0 exactly: Spark 3.5.4 / Python 3.11 / Scala 2.12 / Java 17.
# Code that runs here ports 1:1 into a Glue 5.0 job.
FROM public.ecr.aws/glue/aws-glue-libs:5

# The base image runs as user "hadoop"; switch to root only to install dev deps.
USER root

WORKDIR /home/hadoop/workspace

# Dev-only tooling (pytest, debugger, jupyter). Runtime Spark/Glue libs are
# already in the base image — do NOT reinstall pyspark, it must match Glue.
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

USER hadoop

# GAE python zip is added to the path at runtime by bootstrap_spark.py.
ENV PYTHONPATH=/home/hadoop/workspace:${PYTHONPATH}

CMD ["bash"]
