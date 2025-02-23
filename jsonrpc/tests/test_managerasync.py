import sys

from ..dispatcher import Dispatcher
from ..managerasync import JSONRPCResponseManagerAsync
from ..jsonrpc2 import (
    JSONRPC20BatchRequest,
    JSONRPC20BatchResponse,
    JSONRPC20Request,
    JSONRPC20Response,
)
from ..jsonrpc1 import JSONRPC10Request, JSONRPC10Response
from ..exceptions import JSONRPCDispatchException

if sys.version_info < (3, 3):
    from mock import MagicMock
else:
    from unittest.mock import MagicMock

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest


class TestJSONRPCResponseManagerAsync(unittest.TestCase):
    def setUp(self):
        def raise_(e):
            raise e

        self.long_time_method = MagicMock()
        self.dispatcher = Dispatcher()
        self.dispatcher["add"] = sum
        self.dispatcher["multiply"] = lambda a, b: a * b
        self.dispatcher["list_len"] = len
        self.dispatcher["101_base"] = lambda **kwargs: int("101", **kwargs)
        self.dispatcher["error"] = lambda: raise_(
            KeyError("error_explanation"))
        self.dispatcher["type_error"] = lambda: raise_(
            TypeError("TypeError inside method"))
        self.dispatcher["long_time_method"] = self.long_time_method
        self.dispatcher["dispatch_error"] = lambda x: raise_(
            JSONRPCDispatchException(code=4000, message="error",
                                     data={"param": 1}))

        @self.dispatcher.add_method(context_arg="context")
        def return_json_rpc_id(context):
            return context["request"]._id

    async def test_dispatch_error(self):
        request = JSONRPC20Request("dispatch_error", ["test"], _id=0)
        response = await JSONRPCResponseManagerAsync.handle(request.json, self.dispatcher)
        self.assertTrue(isinstance(response, JSONRPC20Response))
        self.assertEqual(response.error["message"], "error")
        self.assertEqual(response.error["code"], 4000)
        self.assertEqual(response.error["data"], {"param": 1})

    async def test_returned_type_response(self):
        request = JSONRPC20Request("add", [[]], _id=0)
        response = await JSONRPCResponseManagerAsync.handle(request.json, self.dispatcher)
        self.assertTrue(isinstance(response, JSONRPC20Response))

    async def test_returned_type_butch_response(self):
        request = JSONRPC20BatchRequest(
            JSONRPC20Request("add", [[]], _id=0))
        response = await JSONRPCResponseManagerAsync.handle(request.json, self.dispatcher)
        self.assertTrue(isinstance(response, JSONRPC20BatchResponse))

    async def test_returned_type_response_rpc10(self):
        request = JSONRPC10Request("add", [[]], _id=0)
        response = await JSONRPCResponseManagerAsync.handle(request.json, self.dispatcher)
        self.assertTrue(isinstance(response, JSONRPC10Response))

    async def test_parse_error(self):
        req = '{"jsonrpc": "2.0", "method": "foobar, "params": "bar", "baz]'
        response = await JSONRPCResponseManagerAsync.handle(req, self.dispatcher)
        self.assertTrue(isinstance(response, JSONRPC20Response))
        self.assertEqual(response.error["message"], "Parse error")
        self.assertEqual(response.error["code"], -32700)

    async def test_invalid_request(self):
        req = '{"jsonrpc": "2.0", "method": 1, "params": "bar"}'
        response = await JSONRPCResponseManagerAsync.handle(req, self.dispatcher)
        self.assertTrue(isinstance(response, JSONRPC20Response))
        self.assertEqual(response.error["message"], "Invalid Request")
        self.assertEqual(response.error["code"], -32600)

    async def test_method_not_found(self):
        request = JSONRPC20Request("does_not_exist", [[]], _id=0)
        response = await JSONRPCResponseManagerAsync.handle(request.json, self.dispatcher)
        self.assertTrue(isinstance(response, JSONRPC20Response))
        self.assertEqual(response.error["message"], "Method not found")
        self.assertEqual(response.error["code"], -32601)

    async def test_invalid_params(self):
        request = JSONRPC20Request("add", {"a": 0}, _id=0)
        response = await JSONRPCResponseManagerAsync.handle(request.json, self.dispatcher)
        self.assertTrue(isinstance(response, JSONRPC20Response))
        self.assertEqual(response.error["message"], "Invalid params")
        self.assertEqual(response.error["code"], -32602)
        self.assertIn(response.error["data"]["message"], [
            'sum() takes no keyword arguments',
            "sum() got an unexpected keyword argument 'a'",
            'sum() takes at least 1 positional argument (0 given)',
        ])

    async def test_invalid_params_custom_function(self):
        request = JSONRPC20Request("multiply", [0], _id=0)
        response = await JSONRPCResponseManagerAsync.handle(request.json, self.dispatcher)
        self.assertTrue(isinstance(response, JSONRPC20Response))
        self.assertEqual(response.error["message"], "Invalid params")
        self.assertEqual(response.error["code"], -32602)

        request = JSONRPC20Request("multiply", [0, 1, 2], _id=0)
        response = await JSONRPCResponseManagerAsync.handle(request.json, self.dispatcher)
        self.assertTrue(isinstance(response, JSONRPC20Response))
        self.assertEqual(response.error["message"], "Invalid params")
        self.assertEqual(response.error["code"], -32602)

        request = JSONRPC20Request("multiply", {"a": 1}, _id=0)
        response = await JSONRPCResponseManagerAsync.handle(request.json, self.dispatcher)
        self.assertTrue(isinstance(response, JSONRPC20Response))
        self.assertEqual(response.error["message"], "Invalid params")
        self.assertEqual(response.error["code"], -32602)

        request = JSONRPC20Request("multiply", {"a": 1, "b": 2, "c": 3}, _id=0)
        response = await JSONRPCResponseManagerAsync.handle(request.json, self.dispatcher)
        self.assertTrue(isinstance(response, JSONRPC20Response))
        self.assertEqual(response.error["message"], "Invalid params")
        self.assertEqual(response.error["code"], -32602)

    async def test_server_error(self):
        request = JSONRPC20Request("error", _id=0)
        response = await JSONRPCResponseManagerAsync.handle(request.json, self.dispatcher)
        self.assertTrue(isinstance(response, JSONRPC20Response))
        self.assertEqual(response.error["message"], "Server error")
        self.assertEqual(response.error["code"], -32000)
        self.assertEqual(response.error["data"]['type'], "KeyError")
        self.assertEqual(
            response.error["data"]['args'], ('error_explanation',))
        self.assertEqual(
            response.error["data"]['message'], "'error_explanation'")

    async def test_notification_calls_method(self):
        request = JSONRPC20Request("long_time_method", is_notification=True)
        response = await JSONRPCResponseManagerAsync.handle(request.json, self.dispatcher)
        self.assertEqual(response, None)
        self.long_time_method.assert_called_once_with()

    async def test_notification_does_not_return_error_does_not_exist(self):
        request = JSONRPC20Request("does_not_exist", is_notification=True)
        response = await JSONRPCResponseManagerAsync.handle(request.json, self.dispatcher)
        self.assertEqual(response, None)

    async def test_notification_does_not_return_error_invalid_params(self):
        request = JSONRPC20Request("add", {"a": 0}, is_notification=True)
        response = await JSONRPCResponseManagerAsync.handle(request.json, self.dispatcher)
        self.assertEqual(response, None)

    async def test_notification_does_not_return_error(self):
        request = JSONRPC20Request("error", is_notification=True)
        response = await JSONRPCResponseManagerAsync.handle(request.json, self.dispatcher)
        self.assertEqual(response, None)

    async def test_type_error_inside_method(self):
        request = JSONRPC20Request("type_error", _id=0)
        response = await JSONRPCResponseManagerAsync.handle(request.json, self.dispatcher)
        self.assertTrue(isinstance(response, JSONRPC20Response))
        self.assertEqual(response.error["message"], "Server error")
        self.assertEqual(response.error["code"], -32000)
        self.assertEqual(response.error["data"]['type'], "TypeError")
        self.assertEqual(
            response.error["data"]['args'], ('TypeError inside method',))
        self.assertEqual(
            response.error["data"]['message'], 'TypeError inside method')

    async def test_invalid_params_before_dispatcher_error(self):
        request = JSONRPC20Request(
            "dispatch_error", ["invalid", "params"], _id=0)
        response = await JSONRPCResponseManagerAsync.handle(request.json, self.dispatcher)
        self.assertTrue(isinstance(response, JSONRPC20Response))
        self.assertEqual(response.error["message"], "Invalid params")
        self.assertEqual(response.error["code"], -32602)

    async def test_setting_json_rpc_id_in_context(self):
        request = JSONRPC20Request("return_json_rpc_id", _id=42)
        response = await JSONRPCResponseManagerAsync.handle(request.json, self.dispatcher,
                                                 context={})
        self.assertEqual(response.data["result"], 42)
