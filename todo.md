
Make sure everything in image service is working or at leats make sense, file by file, look into file handler, transactions, and company router when necessary.

Make sure the docker files, docker compose and nginx make sense, for all services

Add/verify image-orphan cleanup cron job in image-service :
                        # image-service/cleanup_job.py
                        @app.post("/admin/cleanup-orphans")
                        async def cleanup_orphans(backend_url: str):
                            """
                            1. Call backend API to get list of valid (company_uuid, extension) pairs
                            2. List all objects in MinIO bucket
                            3. Delete objects not in the valid list
                            """
                            
                            # Get valid images from backend
                            async with httpx.AsyncClient() as client:
                                response = await client.get(f"{backend_url}/api/v1/admin/image-inventory")
                                valid_images = response.json()  # [{"uuid": "...", "ext": ".jpg"}, ...]
                            
                            valid_filenames = {f"{img['uuid']}{img['ext']}" for img in valid_images}
                            
                            # List all objects in MinIO
                            objects = minio_client.list_objects(settings.minio_bucket, recursive=True)
                            
                            deleted_count = 0
                            for obj in objects:
                                if obj.object_name not in valid_filenames:
                                    # Orphan found - delete it
                                    minio_client.remove_object(settings.minio_bucket, obj.object_name)
                                    deleted_count += 1
                                    logger.info("orphan_deleted", object_name=obj.object_name)
                            
                            return {"deleted_count": deleted_count, "valid_count": len(valid_filenames)}


Local integration testing:manually make sure everything is working, is an small app for now so unit testing is just for show

Automation scripts: update init_backend.sh and any startup jobs to create buckets, run migrations, seed inventory.

Kubernetes deployment: create manifests/helm, test in k8s (move this step earlier if you want to test k8s before deleting comments — see variant below).

Micro-optimizations if necessary, do this module by module having in cosnideration the topic of the video you are planning to record

Record explanatory videos / docs: record short walkthroughs to show you knwo what you you know and also people can see you know english.

README: update to reflect final deployment and operation details.


