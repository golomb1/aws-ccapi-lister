# AWS CCAPI Lister

Utility script that enumerates AWS resources through the Cloud Control API.

## Prerequisites

* Python 3.9+
* AWS credentials with permissions to call Cloud Control

Install dependencies with:

```bash
pip install -r requirements.txt
```

## Usage

Invoke the collector with one or more CloudFormation resource type names. The
script automatically follows dependencies for resource types that require a
``ResourceModel`` payload (for example, ``AWS::Lambda::Url``).

```bash
python ccapi_lister.py \
  AWS::EC2::Instance \
  AWS::EC2::SpotFleet \
  AWS::AutoScaling::AutoScalingGroup \
  AWS::ECS::Cluster \
  AWS::ECS::Service \
  AWS::EKS::Cluster \
  AWS::EKS::FargateProfile \
  AWS::ECR::Repository \
  AWS::Lambda::Function \
  AWS::ElasticBeanstalk::Application \
  AWS::Lightsail::Instance \
  AWS::Lightsail::Container \
  AWS::S3::Bucket \
  AWS::EC2::VPC \
  AWS::EC2::EIP
```

Results are written to STDOUT in JSON format by default. Use ``--output text``
for a human friendly format, ``--profile`` to select an AWS CLI profile, and
``--region`` to pin the AWS region.
