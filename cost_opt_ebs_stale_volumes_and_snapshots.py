import boto3

def lambda_handler(event, context):
    ec2 = boto3.client('ec2')

    # Get all active EC2 instance IDs (running and stopped)
    instances_response = ec2.describe_instances(Filters=[
        {'Name': 'instance-state-name', 'Values': ['running', 'stopped']}
    ])
    active_instance_ids = set()
    running_instance_ids = set()

    # Extract instance IDs and separate running/stopped instances
    for reservation in instances_response['Reservations']:
        for instance in reservation['Instances']:
            active_instance_ids.add(instance['InstanceId'])
            if instance['State']['Name'] == 'running':
                running_instance_ids.add(instance['InstanceId'])

    # Part 1: Delete unused snapshots (original functionality)
    response = ec2.describe_snapshots(OwnerIds=['self'])
    for snapshot in response['Snapshots']:
        snapshot_id = snapshot['SnapshotId']
        volume_id = snapshot.get('VolumeId')

        if not volume_id:
            # Delete the snapshot if it's not attached to any volume
            ec2.delete_snapshot(SnapshotId=snapshot_id)
            print(f"Deleted EBS snapshot {snapshot_id} as it was not attached to any volume.")
        else:
            # Check if the volume still exists
            try:
                volume_response = ec2.describe_volumes(VolumeIds=[volume_id])
                if not volume_response['Volumes'][0]['Attachments']:
                    ec2.delete_snapshot(SnapshotId=snapshot_id)
                    print(f"Deleted EBS snapshot {snapshot_id} as it was taken from a volume not attached to any running instance.")
            except ec2.exceptions.ClientError as e:
                if e.response['Error']['Code'] == 'InvalidVolume.NotFound':
                    # The volume associated with the snapshot is not found (it might have been deleted)
                    ec2.delete_snapshot(SnapshotId=snapshot_id)
                    print(f"Deleted EBS snapshot {snapshot_id} as its associated volume was not found.")

    # Part 2: Delete unused volumes
    volumes_response = ec2.describe_volumes()
    for volume in volumes_response['Volumes']:
        volume_id = volume['VolumeId']
        attachments = volume['Attachments']
        
        if not attachments:
            # Volume is not attached to any instance
            ec2.delete_volume(VolumeId=volume_id)
            print(f"Deleted unattached EBS volume {volume_id}")
        else:
            # Check if the attached instance is running or stopped
            for attachment in attachments:
                instance_id = attachment['InstanceId']
                if instance_id not in running_instance_ids:
                    # Volume is attached to a stopped instance (optional deletion)
                    # You might want to skip this if you want to keep volumes for stopped instances
                    ec2.delete_volume(VolumeId=volume_id)
                    print(f"Deleted EBS volume {volume_id} as it was attached to stopped instance {instance_id}")
                    break

    return {
        'statusCode': 200,
        'body': 'Cleanup completed successfully'
    }