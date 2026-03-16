import os
import json

def main():
    # The JSON file will be stored in the scripts directory, alongside this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    creds_path = os.path.join(script_dir, 'aws_credentials.json')

    # Important: if the JSON is already there, we do nothing and silently pass.
    # This prevents asking every time setup.bat/sh is run.
    if os.path.exists(creds_path):
        return

    print("\n" + "="*50)
    print("      Tenant-VLite AWS Onboarding Setup")
    print("="*50)
    print("It looks like you are missing AWS credentials.")
    print("Please provide your keys to configure the environment.")
    print("These will be saved locally in scripts/aws_credentials.json\n")

    try:
        aws_access_key_id = input("Enter AWS Access Key ID: ").strip()
        aws_secret_access_key = input("Enter AWS Secret Access Key: ").strip()
    except KeyboardInterrupt:
        print("\n\n[SETUP] Onboarding aborted by user.")
        return

    # Basic validations
    if not aws_access_key_id or not aws_secret_access_key:
        print("\n[ERROR] Both Access Key ID and Secret Access Key must be provided.")
        print("Please run the setup again.\n")
        return

    creds = {
        "AWS_ACCESS_KEY_ID": aws_access_key_id,
        "AWS_SECRET_ACCESS_KEY": aws_secret_access_key
    }

    try:
        with open(creds_path, 'w') as f:
            json.dump(creds, f, indent=4)
        print(f"\n[SUCCESS] AWS credentials successfully saved to {creds_path}\n")
    except Exception as e:
        print(f"\n[ERROR] Could not save credentials. Reason: {e}\n")

if __name__ == "__main__":
    main()
