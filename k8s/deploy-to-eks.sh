#!/bin/bash
set -e

AWS_REGION="ap-northeast-3"
ECR_REPO_NAME="jmeter-snowflake"
CLUSTER_NAME="jmeter-cluster"
NODE_COUNT=10
NODE_TYPE="m5.xlarge"

echo "============================================"
echo "AWS EKS JMeter Distributed Test Setup"
echo "============================================"
echo "Nodes: ${NODE_COUNT}"
echo "Each Node: 50 threads, 50 connection pools"
echo "Total: 500 threads, 500 connection pools"
echo "============================================"

echo ""
echo "Step 1: Create ECR Repository"
aws ecr create-repository --repository-name ${ECR_REPO_NAME} --region ${AWS_REGION} 2>/dev/null || true

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"

echo ""
echo "Step 2: Build and Push Docker Image"
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

docker build -t ${ECR_REPO_NAME}:latest .
docker tag ${ECR_REPO_NAME}:latest ${ECR_URI}:latest
docker push ${ECR_URI}:latest

echo ""
echo "Step 3: Create EKS Cluster (if not exists)"
eksctl get cluster --name ${CLUSTER_NAME} --region ${AWS_REGION} 2>/dev/null || \
eksctl create cluster \
    --name ${CLUSTER_NAME} \
    --region ${AWS_REGION} \
    --node-type ${NODE_TYPE} \
    --nodes ${NODE_COUNT} \
    --nodes-min ${NODE_COUNT} \
    --nodes-max ${NODE_COUNT}

echo ""
echo "Step 4: Update kubeconfig"
aws eks update-kubeconfig --name ${CLUSTER_NAME} --region ${AWS_REGION}

echo ""
echo "Step 5: Update deployment with ECR URI"
sed -i.bak "s|YOUR_ECR_REPO/jmeter-snowflake:latest|${ECR_URI}:latest|g" k8s-deployment.yaml

echo ""
echo "Step 6: Deploy to Kubernetes"
kubectl apply -f k8s-deployment.yaml

echo ""
echo "Step 7: Wait for pods to be ready"
kubectl wait --for=condition=ready pod -l app=jmeter-worker -n jmeter-test --timeout=300s

echo ""
echo "============================================"
echo "Deployment Complete!"
echo "============================================"
echo ""
echo "Monitor pods:  kubectl get pods -n jmeter-test -w"
echo "View logs:     kubectl logs -f -l app=jmeter-worker -n jmeter-test"
echo "Get results:   ./collect-results.sh"
