you are an expert in building interactive table demos in Snowflake. 
Me and one of my colleagues worked on a POC that reads data from an interactive table, did a performance testing using JMeter running on Kubernetese cluster .
This code is available in this directory:
/Users/rnellikal/Documents/my_workspace/coco_ws/NiCE/05_interactive_poc/Snowflake_Interactive_WH_POC
This POC just do reading from an interactive warehouse. 

Now I want to introduce writting into this underlying table using Kafka streaming (Snowpipe streaming V2)
I want you to look at following snowflake quickstart to understand how we can set up a Kafka streaming using snowpipe streaming V2 to snowflake interactive tables. 
https://www.snowflake.com/en/developers/guides/kafka-interactive-tables-streaming/
Using the above quick start as a template, I want you to build something like below:
I want to ingest around 25MB of data into this table (trying to simulate 6-7K events per second that happens at customer tables).
This is the interactive table I want to use for this demo:
INTERACTIVE_DEMO.TPCH_INTERACTIVE.ORDERS_INTERACTIVE (you may need to modify the quries inside Snowflake_Performance_Test_V2.jmx and update the table name)
The warehouse is TPCH_INTERACTIVE_WH
