"""Authenticated actor-private companion endpoints. Inference runs in workers."""
from fastapi import Depends
from .assistant import (ActionDecision, CancelReply, CompanionRepository, ConversationRequest,
                        MessageRequest, TaskUpdate, catalog)


def install_companion_routes(app, store, current):
    repository = CompanionRepository(store)

    @app.get("/api/v1/companion/catalog")
    def companion_catalog(user=Depends(current)):
        return catalog()

    @app.get("/api/v1/companion/conversations")
    def conversations(user=Depends(current)):
        return {"items": repository.list(user)}

    @app.post("/api/v1/companion/conversations", status_code=201)
    def create_conversation(payload: ConversationRequest, user=Depends(current)):
        return repository.create(payload, user)

    @app.get("/api/v1/companion/conversations/{conversation_id}")
    @app.get("/api/v1/companion/conversations/{conversation_id}/messages")
    def conversation(conversation_id: str, user=Depends(current)):
        return repository.get(conversation_id, user)

    @app.post("/api/v1/companion/conversations/{conversation_id}/messages", status_code=202)
    def send_message(conversation_id: str, payload: MessageRequest, user=Depends(current)):
        return repository.message(conversation_id, payload, user)

    @app.post("/api/v1/companion/conversations/{conversation_id}/cancel")
    def cancel(conversation_id: str, payload: CancelReply, user=Depends(current)):
        return repository.cancel(conversation_id, payload, user)

    @app.post("/api/v1/companion/conversations/{conversation_id}/actions/{action_id}/confirm")
    def confirm(conversation_id: str, action_id: str, payload: ActionDecision, user=Depends(current)):
        return repository.decide(conversation_id, action_id, payload, user, confirm=True)

    @app.post("/api/v1/companion/conversations/{conversation_id}/actions/{action_id}/reject")
    def reject(conversation_id: str, action_id: str, payload: ActionDecision, user=Depends(current)):
        return repository.decide(conversation_id, action_id, payload, user, confirm=False)

    @app.get("/api/v1/companion/tasks")
    def tasks(user=Depends(current)):
        return {"items": repository.list(user, "companion_task")}

    @app.put("/api/v1/companion/tasks/{task_id}")
    def update_task(task_id: str, payload: TaskUpdate, user=Depends(current)):
        return repository.update_task(task_id, payload, user)
