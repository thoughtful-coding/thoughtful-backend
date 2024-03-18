# Use the AWS Lambda Python runtime as a parent image
FROM public.ecr.aws/lambda/python:3.11

# Install the required packages
COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install -r requirements.txt

# Copy the function code
COPY src/ ${LAMBDA_TASK_ROOT}


CMD ["aws_src_sample.hello_world.lambda_handler"]
