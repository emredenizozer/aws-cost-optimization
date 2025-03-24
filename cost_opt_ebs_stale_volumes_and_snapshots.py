import boto3
from botocore.exceptions import ClientError

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
    
    # Part 1: Delete unused snapshots
    print("Step 1: Cleaning up unused snapshots")
    snapshots_response = ec2.describe_snapshots(OwnerIds=['self'])
    
    # Get all volumes that are currently attached to instances
    attached_volumes = set()
    volumes_response = ec2.describe_volumes(Filters=[
        {'Name': 'status', 'Values': ['in-use']}
    ])
    for volume in volumes_response['Volumes']:
        attached_volumes.add(volume['VolumeId'])
    
    for snapshot in snapshots_response['Snapshots']:
        snapshot_id = snapshot['SnapshotId']
        volume_id = snapshot.get('VolumeId')
        
        try:
            if not volume_id:
                # Delete the snapshot if it's not attached to any volume
                ec2.delete_snapshot(SnapshotId=snapshot_id)
                print(f"Deleted snapshot {snapshot_id} (no volume associated)")
            elif volume_id not in attached_volumes:
                # Check if the volume exists at all
                try:
                    ec2.describe_volumes(VolumeIds=[volume_id])
                    # Volume exists but is not attached - delete snapshot
                    ec2.delete_snapshot(SnapshotId=snapshot_id)
                    print(f"Deleted snapshot {snapshot_id} (volume {volume_id} exists but is not attached)")
                except ec2.exceptions.ClientError as e:
                    if e.response['Error']['Code'] == 'InvalidVolume.NotFound':
                        # Volume doesn't exist - delete snapshot
                        ec2.delete_snapshot(SnapshotId=snapshot_id)
                        print(f"Deleted snapshot {snapshot_id} (volume {volume_id} not found)")
        except ClientError as e:
            print(f"Error deleting snapshot {snapshot_id}: {e}")
    
    # Part 2: Delete unused volumes
    print("\nStep 2: Cleaning up unused volumes")
    volumes_response = ec2.describe_volumes(Filters=[
        {'Name': 'status', 'Values': ['available']}
    ])
    
    for volume in volumes_response['Volumes']:
        volume_id = volume['VolumeId']
        try:
            ec2.delete_volume(VolumeId=volume_id)
            print(f"Deleted volume {volume_id}")
        except ClientError as e:
            print(f"Error deleting volume {volume_id}: {e}")
    
    return {
        'statusCode': 200,
        'body': 'Cleanup completed successfully'
    }