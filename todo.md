
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


Circuit breaker: implement, fix bugs, integrate into backend client:

                            # backend/app/utils/image_service_client.py
                            from tenacity import retry, stop_after_attempt, wait_exponential

                            class ImageServiceCircuitBreaker:
                                def __init__(self):
                                    self.failure_count = 0
                                    self.last_failure_time = None
                                    self.is_open = False
                                    self.threshold = 5
                                    self.timeout = 60  # seconds
                                
                                def call_allowed(self) -> bool:
                                    if not self.is_open:
                                        return True
                                    
                                    # Check if timeout has passed
                                    if time.time() - self.last_failure_time > self.timeout:
                                        self.is_open = False
                                        self.failure_count = 0
                                        return True
                                    
                                    return False
                                
                                def record_success(self):
                                    self.failure_count = 0
                                    self.is_open = False
                                
                                def record_failure(self):
                                    self.failure_count += 1
                                    self.last_failure_time = time.time()
                                    
                                    if self.failure_count >= self.threshold:
                                        self.is_open = True
                                        logger.error("circuit_breaker_opened", 
                                                    failure_count=self.failure_count)

                            circuit_breaker = ImageServiceCircuitBreaker()

                            class ImageServiceClient:
                                @retry(
                                    stop=stop_after_attempt(3),
                                    wait=wait_exponential(multiplier=1, min=1, max=10)
                                )
                                async def upload_image(self, file_bytes, filename, content_type, user_id):
                                    if not circuit_breaker.call_allowed():
                                        raise ImageServiceError("Circuit breaker is open - service unavailable")
                                    
                                    try:
                                        response = await self.client.post("/upload", ...)
                                        circuit_breaker.record_success()
                                        return response.json()
                                    except Exception as e:
                                        circuit_breaker.record_failure()
                                        raise

Local integration testing:manually make sure everything is working, is an small app for now so unit testing is just for show

Automation scripts: update init_backend.sh and any startup jobs to create buckets, run migrations, seed inventory.

Kubernetes deployment: create manifests/helm, test in k8s (move this step earlier if you want to test k8s before deleting comments — see variant below).

Micro-optimizations if necessary, do this module by module having in cosnideration the topic of the video you are planning to record

Record explanatory videos / docs: record short walkthroughs to show you knwo what you you know and also people can see you know english.

README: update to reflect final deployment and operation details.


