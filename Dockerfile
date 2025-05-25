# Use the AWS Lambda Python runtime as a parent image
FROM public.ecr.aws/lambda/python:3.12

# Install the required packages
COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install -r requirements.txt

# Copy the function code
COPY src/ ${LAMBDA_TASK_ROOT}


CMD ["aws_src_sample.lambdas.s3_put_lambda.s3_put_lambda_handler"]
