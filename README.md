# Online queue with Streamlit, centralized Google Sheets backend and Courier notification system

This is an example of poor man's web project. Feel free to deploy it yourself or draw inspiration.

## 0. Setting up the project

Clone the repository, setup python venv and install the requirements:
```shell
git clone https://github.com/ViktorooReps/streamlit-queue.git
cd streamlit-queue
virtualenv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create the directory for secrets:
```shell
mkdir .streamlit
touch .streamlit/secrets.toml
```

## 1. Setting up Google Sheets backend

Go to Google Sheets, create new spreadsheet and add 2 worksheets:

...one with accounts....
![image](https://user-images.githubusercontent.com/56936206/226171403-8984d948-db69-4538-9958-4f90292bc972.png)

...and another with the actual queue...
![image](https://user-images.githubusercontent.com/56936206/226171454-bfff0bb6-2db8-4d32-9f44-fce2b6bd3ab7.png)


The bottom of your spreadsheet should look like this:
![image](https://user-images.githubusercontent.com/56936206/226171505-7965a649-a222-467d-a0ea-3fc8b96effe0.png)


Fill in Accounts sheet with the names of the people that will use the queue, as well as their Telegram accounts (optional).


Now go to Google Console and create new project. Then you will need to go to Service Accounts:
![image](https://user-images.githubusercontent.com/56936206/226171751-5393c9d7-80aa-4a27-8344-61ad91130aa9.png)

Create service account, and then add a new JSON key:
![image](https://user-images.githubusercontent.com/56936206/226171954-51888815-48aa-465d-9d32-dce4491d1672.png)

Next, you will need to enable Google Sheets API. Search for it in the search bar, click on it and enable it.
![image](https://user-images.githubusercontent.com/56936206/226172218-9a8d90af-0b93-421d-b556-741071f5ff47.png)

Finally, go to your spreadsheet and add your service account with the Share button.

## 2. Configuring Courier notifications

TODO

## 3. Deploying to streamlit

TODO
 
