import base64
import httpx

from app.core.exceptions import GitHubAPIError


class GitHubService:
    BASE_URL = "https://api.github.com"

    @staticmethod
    def _headers(access_token: str) -> dict:
        return {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    @staticmethod
    def _handle_error(response: httpx.Response) -> None:
        if response.is_success:
            return

        try:
            error_data = response.json()
        except ValueError:
            error_data = {}

        message = error_data.get(
            "message",
            "GitHub API request failed.",
        )

        raise GitHubAPIError(
            message=message,
            status_code=response.status_code,
            details=error_data,
        )

    async def list_repositories(
        self,
        access_token: str,
    ) -> list[dict]:
        try:
            async with httpx.AsyncClient(
                timeout=30.0
            ) as client:
                response = await client.get(
                    f"{self.BASE_URL}/user/repos",
                    headers=self._headers(access_token),
                    params={
                        "per_page": 100,
                        "sort": "updated",
                    },
                )

            self._handle_error(response)
            return response.json()

        except httpx.RequestError as error:
            raise GitHubAPIError(
                message="Could not connect to GitHub.",
                status_code=503,
                details={"reason": str(error)},
            )

    async def create_repository(
        self,
        access_token: str,
        repo_name: str,
        private: bool = False,
    ) -> dict:
        try:
            async with httpx.AsyncClient(
                timeout=30.0
            ) as client:
                response = await client.post(
                    f"{self.BASE_URL}/user/repos",
                    headers=self._headers(access_token),
                    json={
                        "name": repo_name,
                        "private": private,
                    },
                )

            self._handle_error(response)
            return response.json()

        except httpx.RequestError as error:
            raise GitHubAPIError(
                message="Could not connect to GitHub.",
                status_code=503,
                details={"reason": str(error)},
            )


    async def upload_file(
    self,
    access_token: str,
    owner: str,
    repo_name: str,
    file_path: str,
    file_content: bytes,
    commit_message: str,
    ) -> dict:
        encoded_content = base64.b64encode(
            file_content
        ).decode("utf-8")

        try:
            async with httpx.AsyncClient(
                timeout=30.0
            ) as client:
                response = await client.put(
                    (
                        f"{self.BASE_URL}/repos/"
                        f"{owner}/{repo_name}/contents/"
                        f"{file_path}"
                    ),
                    headers=self._headers(access_token),
                    json={
                        "message": commit_message,
                        "content": encoded_content,
                    },
                )

            self._handle_error(response)
            return response.json()

        except httpx.RequestError as error:
            raise GitHubAPIError(
                message="Could not connect to GitHub.",
                status_code=503,
                details={"reason": str(error)},
            )


    async def read_file(
        self,
        access_token: str,
        owner: str,
        repo_name: str,
        file_path: str,
    ) -> dict:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    (
                        f"{self.BASE_URL}/repos/"
                        f"{owner}/{repo_name}/contents/{file_path}"
                    ),
                    headers=self._headers(access_token),
                )

            self._handle_error(response)
            data = response.json()

            if data.get("type") != "file":
                raise GitHubAPIError(
                    message="The requested path is not a file.",
                    status_code=400,
                )

            encoded_content = data.get("content", "")
            decoded_content = base64.b64decode(
                encoded_content
            ).decode("utf-8")

            return {
                "name": data["name"],
                "path": data["path"],
                "content": decoded_content,
                "url": data["html_url"],
            }

        except UnicodeDecodeError:
            raise GitHubAPIError(
                message="This file is not a readable text file.",
                status_code=400,
            )

        except httpx.RequestError as error:
            raise GitHubAPIError(
                message="Could not connect to GitHub.",
                status_code=503,
                details={"reason": str(error)},
            )

    async def _request(
        self,
        method: str,
        endpoint: str,
        access_token: str,
        **kwargs,
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(
                timeout=60.0
            ) as client:
                response = await client.request(
                    method=method,
                    url=f"{self.BASE_URL}{endpoint}",
                    headers=self._headers(access_token),
                    **kwargs,
                )

            self._handle_error(response)
            return response

        except httpx.RequestError as error:
            raise GitHubAPIError(
                message="Could not connect to GitHub.",
                status_code=503,
                details={"reason": str(error)},
            )


    async def get_repository(
        self,
        access_token: str,
        owner: str,
        repo_name: str,
    ) -> dict:
        response = await self._request(
            method="GET",
            endpoint=f"/repos/{owner}/{repo_name}",
            access_token=access_token,
        )

        return response.json()


    async def upload_files_batch(
        self,
        access_token: str,
        owner: str,
        repo_name: str,
        files: list[tuple[str, bytes]],
        commit_message: str,
    ) -> dict:
        if not files:
            raise GitHubAPIError(
                message="No files were provided.",
                status_code=400,
            )

        repository = await self.get_repository(
            access_token=access_token,
            owner=owner,
            repo_name=repo_name,
        )

        branch = repository["default_branch"]

        try:
            ref_response = await self._request(
                method="GET",
                endpoint=(
                    f"/repos/{owner}/{repo_name}/git/ref/"
                    f"heads/{branch}"
                ),
                access_token=access_token,
            )

        except GitHubAPIError as error:
            if error.status_code not in {404, 409}:
                raise

            first_path, first_content = files[0]

            await self.upload_file(
                access_token=access_token,
                owner=owner,
                repo_name=repo_name,
                file_path=first_path,
                file_content=first_content,
                commit_message=commit_message,
            )

            files = files[1:]

            if not files:
                return {
                    "branch": branch,
                    "uploaded_count": 1,
                    "commit_url": (
                        f"https://github.com/{owner}/{repo_name}"
                    ),
                }

            ref_response = await self._request(
                method="GET",
                endpoint=(
                    f"/repos/{owner}/{repo_name}/git/ref/"
                    f"heads/{branch}"
                ),
                access_token=access_token,
            )

        parent_commit_sha = (
            ref_response.json()["object"]["sha"]
        )

        commit_response = await self._request(
            method="GET",
            endpoint=(
                f"/repos/{owner}/{repo_name}/git/commits/"
                f"{parent_commit_sha}"
            ),
            access_token=access_token,
        )

        base_tree_sha = (
            commit_response.json()["tree"]["sha"]
        )

        tree_entries = []

        for file_path, file_content in files:
            try:
                text_content = file_content.decode("utf-8")

                tree_entries.append(
                    {
                        "path": file_path,
                        "mode": "100644",
                        "type": "blob",
                        "content": text_content,
                    }
                )

            except UnicodeDecodeError:
                blob_response = await self._request(
                    method="POST",
                    endpoint=(
                        f"/repos/{owner}/{repo_name}/git/blobs"
                    ),
                    access_token=access_token,
                    json={
                        "content": base64.b64encode(
                            file_content
                        ).decode("utf-8"),
                        "encoding": "base64",
                    },
                )

                tree_entries.append(
                    {
                        "path": file_path,
                        "mode": "100644",
                        "type": "blob",
                        "sha": blob_response.json()["sha"],
                    }
                )

        tree_response = await self._request(
            method="POST",
            endpoint=(
                f"/repos/{owner}/{repo_name}/git/trees"
            ),
            access_token=access_token,
            json={
                "base_tree": base_tree_sha,
                "tree": tree_entries,
            },
        )

        new_tree_sha = tree_response.json()["sha"]

        new_commit_response = await self._request(
            method="POST",
            endpoint=(
                f"/repos/{owner}/{repo_name}/git/commits"
            ),
            access_token=access_token,
            json={
                "message": commit_message,
                "tree": new_tree_sha,
                "parents": [parent_commit_sha],
            },
        )

        new_commit_sha = (
            new_commit_response.json()["sha"]
        )

        await self._request(
            method="PATCH",
            endpoint=(
                f"/repos/{owner}/{repo_name}/git/refs/"
                f"heads/{branch}"
            ),
            access_token=access_token,
            json={
                "sha": new_commit_sha,
                "force": False,
            },
        )

        return {
            "branch": branch,
            "uploaded_count": len(tree_entries),
            "commit_sha": new_commit_sha,
            "commit_url": (
                f"https://github.com/{owner}/{repo_name}/"
                f"commit/{new_commit_sha}"
            ),
        }

    async def get_repository(
        self,
        access_token: str,
        owner: str,
        repo_name: str,
    ) -> dict:
        response = await self._request(
            method="GET",
            endpoint=f"/repos/{owner}/{repo_name}",
            access_token=access_token,
        )

        return response.json()   

    async def upload_files_batch(
        self,
        access_token: str,
        owner: str,
        repo_name: str,
        files: list[tuple[str, bytes]],
        commit_message: str,
    ) -> dict:
        if not files:
            raise GitHubAPIError(
                message="No files were provided.",
                status_code=400,
            )

        repository = await self.get_repository(
            access_token=access_token,
            owner=owner,
            repo_name=repo_name,
        )

        branch = repository["default_branch"]

        # An empty repository does not have a branch reference.
        # Initialise it using the Contents API.
        try:
            reference_response = await self._request(
                method="GET",
                endpoint=(
                    f"/repos/{owner}/{repo_name}/git/ref/"
                    f"heads/{branch}"
                ),
                access_token=access_token,
            )
        except GitHubAPIError as error:
            if error.status_code not in {404, 409}:
                raise

            first_path, first_content = files[0]

            await self.upload_file(
                access_token=access_token,
                owner=owner,
                repo_name=repo_name,
                file_path=first_path,
                file_content=first_content,
                commit_message=commit_message,
            )

            files = files[1:]

            if not files:
                return {
                    "branch": branch,
                    "uploaded_count": 1,
                    "commit_url": (
                        f"https://github.com/{owner}/{repo_name}"
                    ),
                }

            reference_response = await self._request(
                method="GET",
                endpoint=(
                    f"/repos/{owner}/{repo_name}/git/ref/"
                    f"heads/{branch}"
                ),
                access_token=access_token,
            )

        reference_data = reference_response.json()
        parent_commit_sha = reference_data["object"]["sha"]

        commit_response = await self._request(
            method="GET",
            endpoint=(
                f"/repos/{owner}/{repo_name}/git/commits/"
                f"{parent_commit_sha}"
            ),
            access_token=access_token,
        )

        base_tree_sha = commit_response.json()["tree"]["sha"]

        tree_entries = []

        for file_path, file_content in files:
            try:
                text_content = file_content.decode("utf-8")

                tree_entries.append(
                    {
                        "path": file_path,
                        "mode": "100644",
                        "type": "blob",
                        "content": text_content,
                    }
                )

            except UnicodeDecodeError:
                # Binary files require a blob object.
                blob_response = await self._request(
                    method="POST",
                    endpoint=(
                        f"/repos/{owner}/{repo_name}/git/blobs"
                    ),
                    access_token=access_token,
                    json={
                        "content": base64.b64encode(
                            file_content
                        ).decode("utf-8"),
                        "encoding": "base64",
                    },
                )

                tree_entries.append(
                    {
                        "path": file_path,
                        "mode": "100644",
                        "type": "blob",
                        "sha": blob_response.json()["sha"],
                    }
                )

        tree_response = await self._request(
            method="POST",
            endpoint=f"/repos/{owner}/{repo_name}/git/trees",
            access_token=access_token,
            json={
                "base_tree": base_tree_sha,
                "tree": tree_entries,
            },
        )

        new_tree_sha = tree_response.json()["sha"]

        new_commit_response = await self._request(
            method="POST",
            endpoint=f"/repos/{owner}/{repo_name}/git/commits",
            access_token=access_token,
            json={
                "message": commit_message,
                "tree": new_tree_sha,
                "parents": [parent_commit_sha],
            },
        )

        new_commit = new_commit_response.json()
        new_commit_sha = new_commit["sha"]

        await self._request(
            method="PATCH",
            endpoint=(
                f"/repos/{owner}/{repo_name}/git/refs/"
                f"heads/{branch}"
            ),
            access_token=access_token,
            json={
                "sha": new_commit_sha,
                "force": False,
            },
        )

        return {
            "branch": branch,
            "uploaded_count": len(tree_entries),
            "commit_sha": new_commit_sha,
            "commit_url": (
                f"https://github.com/{owner}/{repo_name}/"
                f"commit/{new_commit_sha}"
            ),
        }

github_service = GitHubService()