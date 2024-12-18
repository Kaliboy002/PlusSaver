from telethon.custom import Message
from telethon.events import CallbackQuery
from telethon.types import PeerChannel, PeerUser, Channel as ChannelInstance
from telethon.errors.rpcerrorlist import FloodWaitError, MediaCaptionTooLongError
from telethon.tl.functions.channels import GetFullChannelRequest, GetParticipantRequest
from telethon.errors.rpcerrorlist import UserNotParticipantError, ChatAdminRequiredError, ChannelPrivateError, UserIsBlockedError, WebpageCurlFailedError, WebpageMediaEmptyError, MediaEmptyError
from abc import ABC, abstractmethod
from re import match
from typing import Iterable, Any
from asyncio import sleep
import logging
import os

from modules.downloaders import Youtube, SoundCloud, Instagram, MediaDownloaded, Pinterest, TikTok, InstagramV2
from modules.downloaders.shcemas import MediasDownloaded, MediaDownloaded
from config import Strings, BotConfig
from modules.handlers.buttons import InlineButtonsData, InlineButtons, TextButtons, TextButtonsString, UrlButtons
from modules.database import User, Channel, Session, engine, Configs, Media
from modules.handlers.app import client
from modules.handlers.step import Step, step_limit, Permission
from modules.regexs import Regexs


logging.basicConfig(filename="log.txt", filemode="a",format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


async def send_media(event, medias: MediaDownloaded | MediasDownloaded) -> None:
    
    if isinstance(medias, MediaDownloaded):
        medias = MediasDownloaded(MEDIAS=[medias])
    
    for media in medias.MEDIAS:
        if media.RESULT is True:
                
            try:
                
                try:
                    message = await client.send_message(event.chat_id, Strings.UPLOADING)
                    media_sended = await client.send_file(event.chat_id, file=media.MEDIA, caption=Strings.media_geted(media.TITLE, media.CAPTION), reply_to=event.id)
                
                except MediaCaptionTooLongError:
                    media_sended = await client.send_file(event.chat_id, file=media.MEDIA, reply_to=event.id)
                    await client.send_message(event.chat_id, message=Strings.media_geted(media.TITLE, media.CAPTION), reply_to=media_sended.id)
                
                except (WebpageCurlFailedError, WebpageMediaEmptyError, MediaEmptyError):
                    await client.send_message(event.chat_id, message=Strings.media_geted(media.TITLE, media.CAPTION, download_url=media.MEDIA), reply_to=event.id, link_preview=False)
                    await message.delete()
                    return
                
                await message.delete()
                
                try:
                    media_saved = await client.send_message(PeerChannel(BotConfig.MEDIAS_CHANNEL_ID), message=media_sended)
                    with Session(engine) as session:
                        media_save = Media(media_downloaded_url=str(event.message.message), message_id=media_saved.id, channel_id=int(BotConfig.MEDIAS_CHANNEL_ID))
                        session.add(media_save)
                        session.commit()
                        session.refresh(media_saved)
                except Exception as e:
                    print(e)
                
            
            except Exception as e:
                print("Error in send_media, error :", e)
        
            try:
                if os.path.exists(media.MEDIA):
                    os.remove(media.MEDIA)
            except Exception as e:
                print(e)
            
            await sleep(0.5)
            
        elif media.RESULT is False:
            await event.reply(Strings.MEDIA_GET_ERROR)
        
        elif media.RESULT is None:
            await event.reply(Strings.MEDIA_NOT_FOUND)


async def check_and_send_media_from_db(event, url: str) -> bool:
    with Session(engine) as session:
        medias = session.query(Media).filter_by(media_downloaded_url=str(url)).all()
        if not medias:
            return False
        
        for media in medias:
        
            try:
                    
                message = await client.get_messages(
                    entity=PeerChannel(int(media.channel_id)),
                    ids=int(media.message_id)
                )
                
                await client.send_message(
                    entity=event.chat_id,
                    message=message,
                    reply_to=event.id
                )
            
            except Exception as e:
                print("Error in check_and_send_media_from_db, error :", e)
                session.delete(media)
                session.commit()
                return False
        
        return True


async def check_join(user_id: int) -> bool:

    with Session(engine) as session:
        channels = session.query(Channel).all()

        if not channels:
            return True

        not_joined = []
        not_admin = []

        for channel in channels:

            try:

                await client(GetParticipantRequest(PeerChannel(channel.channel_id), PeerUser(int(user_id))))

            except UserNotParticipantError:
                not_joined.append(channel)
            
            except (ChatAdminRequiredError, ChannelPrivateError):
                not_admin.append(channel)
                session.delete(channel)

            except Exception as e:
                print(e)
                return True
        
        session.commit()

        for channel in not_admin:
            try:
                await client.send_message((BotConfig.CREATOR_USER_ID), message=Strings.channel_deleted(channel))
            except Exception as e:
                print(e)
        if not_joined:
            await client.send_message(PeerUser(user_id), Strings.JOIN_TO_CHANNELS, buttons=UrlButtons.channels_locked(not_joined))
            return False
        return True


# function for add new users if not database
async def add_user(user_id: int) -> bool:
    
    with Session(engine) as session:

        is_joined = await check_join(user_id)

        user = session.query(User).filter_by(user_id=int(user_id)).first()

        if not user:

            user = User(user_id=int(user_id))

            session.add(user)
            session.commit()

        if is_joined:
            return True
        return False
               

# del user from step
def del_step(user_id: int) -> bool:
    if int(user_id) in step_limit:
        del step_limit[int(user_id)]
        return True
    return False


# send message to users function
async def send_to_users(users_id: Iterable[int], message: Any) -> int:
    secsess = 0

    for user in users_id:
        try:
            
            await client.send_message(entity=PeerUser(user), message=message)
            secsess += 1
            await sleep(0.3)
        except FloodWaitError as e:
            await sleep(e.seconds + 2)
        
        except Exception as e:
            print(e)
        
    return secsess


class HandlerBase(ABC):

    @abstractmethod
    async def user(event) -> None:
        pass


    @abstractmethod
    async def admin(event) -> None:
        pass


class CallBackQueryHandlers(HandlerBase):

    @staticmethod
    async def user(event: CallbackQuery.Event) -> None:

        try:

            data = str(event.data.decode())

            if not await add_user(event.sender_id):
                return
        
            match (data):

                case InlineButtonsData.JOINED_IN_CHANNEL:
                    await event.delete()
                    await client.send_message(event.chat_id, Strings.START_MENU)

        except Exception as e:
            print(e)

    @staticmethod
    async def admin(event: CallbackQuery.Event) -> None:

        try:

            data = str(event.data.decode())

            match(data):

                case InlineButtonsData.BACK_TO_ADMIN:
                    await event.edit(Strings.BACKED, buttons=InlineButtons.ADMIN_PANEL)

                case InlineButtonsData.BOT_STATS:
                    with Session(engine) as session:
                        users = session.query(User).count()
                        channels = session.query(Channel).count()
                    
                    await event.answer(Strings.bot_stats(users, channels), alert=True)

                case InlineButtonsData.ADMIN_SETTING_PANEL:
                    await event.edit(Strings.SELECT, buttons=InlineButtons.ADMIN_SETTING)

                case InlineButtonsData.USER_SETTING_PANEL:
                    await event.edit(Strings.SELECT, buttons=InlineButtons.USER_SETTING)

                case InlineButtonsData.CHANNEL_PANEL:
                    with Session(engine) as session:
                        channels = session.query(Channel).all()
                    await event.edit(Strings.SELECT, buttons=InlineButtons.channels_panel(channels))

                case InlineButtonsData.SEND_PANEL:
                    await event.edit(Strings.SELECT, buttons=InlineButtons.SEND_PANEL)

                case InlineButtonsData.SEND_TO_USER:
                    step = Permission(PART=Step.SEND_TO_USER)
                    step_limit[int(event.sender_id)] = step
                    await event.reply(Strings.ENTER_USER_ID)

                case InlineButtonsData.SEND_TO_USERS:
                    step = Permission(PART=Step.SEND_TO_USERS)
                    step_limit[int(event.sender_id)] = step
                    await event.reply(Strings.ENTER_MESSAGE)

                case InlineButtonsData.CHANGE_CONFIGS:
                    await event.edit(Strings.SELECT, buttons=InlineButtons.CONFIGS_PANEL)

                case InlineButtonsData.ADD_ADMIN | InlineButtonsData.DELETE_ADMIN:
                    step = Permission(PART=Step.ADD_ADMIN if data == InlineButtonsData.ADD_ADMIN else Step.DELETE_ADMIN)
                    step_limit[int(event.sender_id)] = step
                    await event.edit(Strings.ENTER_USER_ID)

                case InlineButtonsData.SHOW_ADMINS:
                    with Session(engine) as session:
                        admins = session.query(User).filter_by(is_admin=True).all()
                    await event.edit(Strings.show_admins(admins), buttons=InlineButtons.ADMIN_SETTING, parse_mode='html')

                case InlineButtonsData.ADD_CHANNEL:
                    step = Permission(PART=Step.ADD_CHANNEL)
                    step_limit[int(event.sender_id)] = step
                    await event.edit(Strings.ADD_CHANNEL)

                case data if (str(data).startswith(InlineButtonsData.DELETE_CHANNEL)):
                    channel_id = str(data).replace(InlineButtonsData.DELETE_CHANNEL, '')
                    with Session(engine) as session:
                        channel = session.query(Channel).filter_by(channel_id=int(channel_id)).first()

                        if channel:
                            session.delete(channel)
                            session.commit()
                            channels = session.query(Channel).all()
                            await event.edit(Strings.DELETED, buttons=InlineButtons.channels_panel(channels))

                case InlineButtonsData.BAN_USER | InlineButtonsData.UNBAN_USER:
                    step = Permission(PART=Step.BAN_USER if data == InlineButtonsData.BAN_USER else Step.UNBAN_USER)
                    step_limit[int(event.sender_id)] = step
                    await event.edit(Strings.ENTER_USER_ID)

                case InlineButtonsData.SHOW_USER_INFO:
                    await event.answer(Strings.NEW_UPDATE)

                case InlineButtonsData.CHANGE_HELP_TEXT:
                    step = Permission(PART=Step.CHANGE_HELP_TEXT)
                    step_limit[int(event.sender_id)] = step
                    await event.edit(Strings.ENTER_TEXT)

                case InlineButtonsData.CHANGE_RULES_TEXT:
                    step = Permission(PART=Step.CHANGE_RULES_TEXT)
                    step_limit[int(event.sender_id)] = step
                    await event.edit(Strings.ENTER_TEXT)

                case InlineButtonsData.CHANGE_TRUST_CHANNEL:
                    step = Permission(PART=Step.CHANGE_SUPPORT_CHANNEL)
                    step_limit[int(event.sender_id)] = step
                    await event.edit(Strings.ENTER_URL)

        
        except Exception as e:
            print(e)


class NewMessageHandlers(HandlerBase):

    @staticmethod
    async def user(event: Message) -> None:

        try:

            text = str(event.message.message)

            if not await add_user(event.sender_id):
                return            
            
            match (text):
                

                case TextButtonsString.START_COMMAND:
                    del_step(event.sender_id)
                    await client.send_message(event.chat_id, Strings.START_MENU, buttons=UrlButtons.ADD_TO_GROUP)

                case TextButtonsString.RULES_COMMAND:
                    with Session(engine) as session:
                        config = session.query(Configs).first()
                    await client.send_message(entity=event.chat_id, message=config.rules_text, parse_mode='markdown')

                case TextButtonsString.HELP_COMMAND:
                    with Session(engine) as session:
                        config = session.query(Configs).first()
                    await client.send_message(entity=event.chat_id, message=config.trust_text, buttons=UrlButtons.trust_channel(), parse_mode="markdown")

                case TextButtonsString.CONTACT_US_COMMAND:
                    await client.send_message(entity=event.chat_id, message=Strings.CONTACT_US, buttons=UrlButtons.CONTACT_US)

                case TextButtonsString.DONATE:
                    await client.send_message(entity=event.chat_id, message=Strings.DONATE)

                case TextButtonsString.CREATOR:
                    await client.send_message(entity=event.chat_id, message=Strings.CREATOR)

        except Exception as e:
            print(e)


    @staticmethod
    async def admin(event: Message) -> None:

        try:
        
            match (str(event.message.message)):

                case "/admin" | "/panel":
                    await client.send_message(entity=event.chat_id, message=Strings.ADMIN_PANEL, buttons=InlineButtons.ADMIN_PANEL)

        except Exception as e:
            print(e)


    @staticmethod
    async def cancel(event: Message) -> None:

        try:
            if str(event.message.message) == "/cancel" and del_step(event.sender_id):    
                await event.reply(Strings.CANCELED)
        except Exception as e:
            print(e)


    @staticmethod
    async def get_url(event: Message) -> None:
        
        url = str(event.message.message)

        match = Regexs(url=url)
        
        if not match.check_all:
            return
        
        try:
        
            if not await check_join(event.sender_id):
                await event.reply(Strings.CHECK_PV)
                return

        except UserIsBlockedError:
            
            await event.reply(Strings.PLEASE_START_BOT_AND_JOIN_CHANNELS)
            return
        
        except Exception as e:
            print(e)


        if match.is_instagram:
            
            message = await event.reply(Strings.PLEASE_WAIT)
            
            if not await check_and_send_media_from_db(event, url):
                
                # instagram_client = Instagram(url)
                instagram_client = InstagramV2(url)
                medias = await instagram_client.download_media()
                await send_media(event, medias)
            
            await message.delete()
                                
        elif match.is_youtube:
            
            message = await event.reply(Strings.PLEASE_WAIT)
            
            if not await check_and_send_media_from_db(event, url):
                
                youtube_client = Youtube(url)
                video = await youtube_client.download_video()
                await send_media(event, video)
            
            await message.delete()
                    
        elif match.is_soundcloud:
            
            message = await event.reply(Strings.PLEASE_WAIT)
            
            if not await check_and_send_media_from_db(event, url):
                
                soundcloud_client = SoundCloud(url)
                music = await soundcloud_client.download_music()
                await send_media(event, music)
            
            await message.delete()

        elif match.is_spotify:
            await event.reply(Strings.COMMING_SOON)

        elif match.is_tiktok:            
            message = await event.reply(Strings.PLEASE_WAIT)
            
            if not await check_and_send_media_from_db(event, url):
                
                tiktok_client = TikTok(url)
                video = await tiktok_client.download_post()
                await send_media(event, video)
            
            await message.delete()

        elif match.is_pinterest:
            message = await event.reply(Strings.PLEASE_WAIT)
            
            if not await check_and_send_media_from_db(event, url):
                
                pinterest_client = Pinterest(url)
                image = await pinterest_client.download_image()
                await send_media(event, image)
            
            await message.delete()


class NewMessageGetInformationsHandlers(HandlerBase):

    @staticmethod
    async def user(event: Message) -> None:

        try:
        
            info = step_limit.get(int(event.sender_id))

            if not info:
                return
            
            # this switch for get information
            
            # match (info.PART):
                
        except Exception as e:
            print(e)


    @staticmethod
    async def admin(event: Message) -> None:

        try:
        
            info = step_limit.get(int(event.sender_id))
            if not info:
                return
            
            match(info.PART):

                case Step.ADD_ADMIN | Step.DELETE_ADMIN:
                    user_id = str(event.message.message)

                    if user_id == str(event.sender_id):
                        await event.reply(Strings.NO_YOU)

                    elif user_id == str(BotConfig.CREATOR_USER_ID):
                        await event.reply(Strings.IS_CREATOR)

                    elif user_id.isnumeric():

                        with Session(engine) as session:
                            user = session.query(User).filter_by(user_id=int(user_id)).first()

                            if user:

                                if user.is_admin:

                                    if info.PART == Step.ADD_ADMIN:
                                        await event.reply(Strings.USER_EXIST)
                                    else:
                                        user.is_admin = False
                                        session.commit()
                                        await event.reply(Strings.DELETED, buttons=InlineButtons.ADMIN_SETTING)
                                        del_step(event.sender_id)
                                else:

                                    if info.PART == Step.ADD_ADMIN:
                                        user.is_admin = True
                                        session.commit()
                                        await event.reply(Strings.ADDED, buttons=InlineButtons.ADMIN_SETTING)
                                        del_step(event.sender_id)
                                    else:
                                        await event.reply(Strings.USER_NOT_EXIST)

                            else:
                                await event.reply(Strings.USER_NOT_EXIST)
                    else:

                        await event.reply(Strings.ENTER_NUMBER)

                case Step.ADD_CHANNEL:
                    if event.forward and (isinstance((channel := await event.forward.get_chat()), ChannelInstance)):
                        try:
                            if channel.admin_rights:
                                with Session(engine) as session:
                                    get_channel = session.query(Channel).filter_by(channel_id=channel.id).first()
                                    
                                    try:

                                        if not get_channel:
                                            channel_info = await client(GetFullChannelRequest(PeerChannel(int(channel.id))))
                                            add_channel = Channel(channel_id=int(channel.id), channel_name=channel.title, channel_url=channel_info.full_chat.exported_invite.link)
                                            session.add(add_channel)
                                            session.commit()
                                            del_step(event.sender_id)
                                            await event.reply(Strings.ADDED, buttons=InlineButtons.ADMIN_PANEL)
                                    
                                        else:
                                            await event.reply(Strings.CHANNEL_ALREADY_EXIST)

                                    except Exception as e:
                                        print(e)
                                        await event.reply(Strings.BOT_NOT_ADMIN)

                            else:
                                await event.reply(Strings.BOT_NOT_ADMIN)

                        except Exception as e:
                            print(e)
                            await event.reply(Strings.ERROR, buttons=InlineButtons.ADMIN_PANEL)
                            del_step(event.sender_id)
                    
                    else:
                        await event.reply(Strings.ADD_CHANNEL)

                case Step.BAN_USER | Step.UNBAN_USER:
                    user_id = str(event.message.message)
                    if user_id.isnumeric():
                        
                        with Session(engine) as session:
                            user = session.query(User).filter_by(user_id=int(user_id)).first()

                            if user:
                                
                                user.is_ban = True if info.PART == Step.BAN_USER else False
                                session.commit()
                                del_step(event.sender_id)
                                await event.reply(Strings.UPDATED, buttons=InlineButtons.USER_SETTING)

                            else:
                                await event.reply(Strings.USER_NOT_EXIST)

                    else:
                        await event.reply(Strings.ENTER_NUMBER)

                case Step.SEND_TO_USER:
                    user_id = str(event.message.message)

                    if user_id.isnumeric():
                        with Session(engine) as session:
                            user = session.query(User).filter_by(user_id=int(user_id)).first()
                        if user:
                            step = Permission(PART=Step.GET_MESSAGE, USER_ID=int(user_id))
                            step_limit[int(event.sender_id)] = step
                            await event.reply(Strings.ENTER_MESSAGE)
                        else:
                            await event.reply(Strings.USER_NOT_EXIST)

                    else:
                        await event.reply(Strings.ENTER_NUMBER)

                case Step.SEND_TO_USERS | Step.GET_MESSAGE:
                    
                    
                    if info.PART == Step.SEND_TO_USERS:
                        with Session(engine) as session:
                            users = session.query(User).all()
                            users = [user.user_id for user in users]

                    else:
                        users = (info.USER_ID, )
                    
                    del_step(event.sender_id)
                    await event.reply(Strings.SENDING, buttons=InlineButtons.SEND_PANEL)
                    sucsess = await send_to_users(users_id=users, message=event.message)
                    await event.reply(Strings.message_sended(success_num=sucsess))

                case Step.SHOW_USER_INFO:
                    await event.reply(Strings.NEW_UPDATE, buttons=InlineButtons.USER_SETTING)
                    del_step(event.sender_id)

                case Step.CHANGE_HELP_TEXT | Step.CHANGE_RULES_TEXT:
                    
                    text = str(event.message.message)

                    if len(text) <= BotConfig.TEXT_LONG:
                        
                        with Session(engine) as session:
                            
                            configs = session.query(Configs).first()

                            if info.PART == Step.CHANGE_HELP_TEXT:
                                configs.trust_text = text
                            else:
                                configs.rules_text = text
                            
                            session.commit()
                            del_step(event.sender_id)
                            await event.reply(Strings.UPDATED, buttons=InlineButtons.CONFIGS_PANEL)

                    else:

                        await event.reply(Strings.TEXT_IS_LONG)

                case Step.CHANGE_SUPPORT_CHANNEL:
                    text = str(event.message.message)
                    if match(r'^(?:https://telegram\.me/|https://t\.me/|t\.me/|telegram\.me/|@)[A-Za-z0-9_+]+', text):
                        with Session(engine) as session:
                            
                            configs = session.query(Configs).first()
                            if text.startswith("@"):
                                text = text.replace("@", "t.me/")
                            configs.support_channel_url = text
                            session.commit()
                        
                        del_step(event.sender_id)
                        await event.reply(Strings.UPDATED, buttons=InlineButtons.CONFIGS_PANEL)
                    
                    else:
                        await event.reply(Strings.ENTER_URL)
                        
        
        except Exception as e:
            print(e)
