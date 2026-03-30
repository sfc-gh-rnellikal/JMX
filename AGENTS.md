# Project: Interactive Warehouse POC
- POC for NiCE customer; Target is the get 700QPS with minimal infrastructure (EKS and interactive warehouse with less number of clusters)
- This POc used jMeter running on EKS cuntainers for load testing
- After the testing, it generates an html report that capture response time from jMeter (client) as well as response time from Snowflake database side
- POC uses snowflake connection -PERSONAL 
- POC uses aws sandbox Oregon region

## Testing Rules
1) spin up the EKS cluster 
2) initiate Kafka ingestion to Interactive tables for 30 minutes ~25MB/Sec rate 
3) start the load testing from EKS cluster for 10 minutes 
4) capture the result 
5) scale down the EKS cluster 
6) Stop Kafka ingestion 
7) Generate html report as per the template, add client side response time as well as server time reponse time to the report 
use information_schema table function to gather response time from snowflake since account_usage.query_history will not have lates data; Make sure report the status of each step and get confirmation before moving to next step
### EKS Cluster
- When spinning up an EKS cluster, always use the existing VPC, subnets, and security groups. Never create a new VPC or subnets.
- Default AWS region: us-west-2 (Oregon)

### Performance Testing
- Default test duration: 10 minutes (600 seconds)
- Collect the .jtl files from each pod immediately after the testing
- Always wait for user confirmation before shutting down the EKS cluster after a test

### HTML Report Generation
- Use the following file as the HTML report template: `Snowflake_Interactive_WH_POC/reports/eks_xsmall_10clusters_30pool_80threads_report.html`
- Preserve the template's layout, styling, and structure. Only replace data values with actual test results.
