import json
from argparse import ArgumentParser

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('path_to_json_credentials')

    args = parser.parse_args()
    creds_file: str = args.path_to_json_credentials

    with open(creds_file) as f:
        creds = json.load(f)

    for secret_name, secret_value in creds.items():
        print(f'credentials.{secret_name} = """{secret_value}"""')
